from datetime import datetime
from http import HTTPStatus
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from requests import Session

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
        self.proxy = proxy

    @staticmethod
    def _login(email: str, password: str, proxy: Optional[str] = None) -> Session:
        session = Session()
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            }
        )
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
            else:
                raise BookingFailed(f"Login error tag present: {soup.text[:200]!r}")
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
            f"Classes response: status={response.status_code} length={len(response.content)}"
        )
        if not response.text.strip():
            raise BookingFailed(
                f"Classes endpoint returned empty body (status={response.status_code})"
            )
        return response.json().get("bookings")

    def book_class(
        self, target_day: datetime, class_id: str, family_id: str | None = None
    ) -> bool:
        box_origin = f"https://{self.box_name}.aimharder.com"
        proxies = (
            {"http": self.proxy, "https": self.proxy} if self.proxy else None
        )
        response = cffi_requests.post(
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
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            },
            cookies=self.session.cookies.get_dict(),
            impersonate="chrome120",
            proxies=proxies,
        )
        logger.info(
            f"Book response: status={response.status_code} length={len(response.content)} body[:200]={response.text[:200]!r}"
        )
        if response.status_code == HTTPStatus.OK:
            if not response.text.strip():
                raise BookingFailed(
                    f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (empty body, status=200)"
                )
            data = response.json()
            book_state = data.get("bookState")
            if book_state == -2:
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if book_state == -12:
                raise BookingFailed(MESSAGE_TOO_SOON_TO_BOOK)
            if isinstance(book_state, int) and book_state < 0:
                raise BookingFailed(
                    f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (bookState={book_state})"
                )
            if data.get("logout"):
                raise BookingFailed(MESSAGE_SESSION_REJECTED)
            if "errorMssg" in data or "errorMssgLang" in data:
                raise BookingFailed(
                    f"{MESSAGE_BOOKING_FAILED_UNKNOWN} ({data.get('errorMssg') or data.get('errorMssgLang')})"
                )
            if book_state == 1 or "id" in data:
                return True
            raise BookingFailed(
                f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (unexpected response, keys={sorted(data.keys())})"
            )
        raise BookingFailed(
            f"{MESSAGE_BOOKING_FAILED_UNKNOWN} (HTTP {response.status_code})"
        )
