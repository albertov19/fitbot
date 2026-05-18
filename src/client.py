from datetime import datetime
from http import HTTPStatus
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi.requests import Session

from constants import (
    LOGIN_ENDPOINT,
    book_endpoint,
    classes_endpoint,
    ERROR_TAG_ID,
)
from exceptions import (
    BookingFailed,
    IncorrectCredentials,
    TooManyWrongAttempts,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
    MESSAGE_SESSION_REJECTED,
    MESSAGE_TOO_SOON_TO_BOOK,
)
from logger import logger


class AimHarderClient:
    def __init__(
        self,
        email: str,
        password: str,
        box_id: int,
        box_name: str,
        proxy: Optional[str] = None,
    ):
        self.session = self._login(email, password, proxy)
        self.box_id = box_id
        self.box_name = box_name

    @staticmethod
    def _login(email: str, password: str, proxy: Optional[str] = None) -> Session:
        session = Session(impersonate="chrome120")
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        session.headers.update({"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
        logger.info(f"Using proxy: {'yes' if proxy else 'no'}")
        response = session.post(
            LOGIN_ENDPOINT,
            data={
                "login": "Log in",
                "mail": email,
                "pw": password,
            },
        )
        logger.info(
            f"Login response: status={response.status_code} length={len(response.content)}"
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser").find(id=ERROR_TAG_ID)
        if soup is not None:
            if TooManyWrongAttempts.key_phrase in soup.text:
                raise TooManyWrongAttempts
            elif IncorrectCredentials.key_phrase in soup.text:
                raise IncorrectCredentials
        logger.info("Logged successfully")
        return session

    def get_classes(self, target_day: datetime, family_id: str | None = None):
        response = self.session.get(
            classes_endpoint(self.box_name),
            params={
                "box": self.box_id,
                "day": target_day.strftime("%Y%m%d"),
                "familyId": family_id,
            },
        )
        logger.info(
            f"Classes response: status={response.status_code} body[:500]={response.text[:500]!r}"
        )
        return response.json().get("bookings")

    def book_class(
        self, target_day: datetime, class_id: str, family_id: str | None = None
    ) -> bool:
        box_origin = f"https://{self.box_name}.aimharder.com"
        response = self.session.post(
            book_endpoint(self.box_name),
            data={
                "id": class_id,
                "day": target_day.strftime("%Y%m%d"),
                "insist": 0,
                "familyId": family_id,
            },
            headers={
                "Origin": box_origin,
                "Referer": f"{box_origin}/schedule",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        logger.info(
            f"Book response: status={response.status_code} body={response.text}"
        )
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            book_state = data.get("bookState")
            if book_state == -2:
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if book_state == -12:
                raise BookingFailed(MESSAGE_TOO_SOON_TO_BOOK)
            if isinstance(book_state, int) and book_state < 0:
                raise BookingFailed(
                    f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (bookState={book_state}, body={data})"
                )
            if data.get("logout"):
                raise BookingFailed(f"{MESSAGE_SESSION_REJECTED} (body={data})")
            if "errorMssg" in data or "errorMssgLang" in data:
                raise BookingFailed(
                    f"{MESSAGE_BOOKING_FAILED_UNKNOWN} ({data.get('errorMssg') or data.get('errorMssgLang')})"
                )
            if book_state == 1 or "id" in data:
                return True
            raise BookingFailed(
                f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (unexpected response, body={data})"
            )
        raise BookingFailed(
            f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (HTTP {response.status_code})"
        )
