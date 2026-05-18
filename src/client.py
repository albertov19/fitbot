import hashlib
from datetime import datetime
from http import HTTPStatus
from typing import Optional

from requests import Session

from constants import (
    LOGIN_ENDPOINT,
    LOGIN_PAGE,
    book_endpoint,
    classes_endpoint,
)
from exceptions import (
    BookingFailed,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
    MESSAGE_SESSION_REJECTED,
    MESSAGE_TOO_SOON_TO_BOOK,
)
from logger import logger


BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


def _stable_fingerprint(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:50]


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
        self._warmup_subdomain()

    def _warmup_subdomain(self) -> None:
        url = f"https://{self.box_name}.aimharder.com/schedule"
        response = self.session.get(url)
        cookie_summary = sorted(
            f"{c.name}@{c.domain}" for c in self.session.cookies
        )
        logger.info(
            f"Warmup response: status={response.status_code} length={len(response.content)} cookies={cookie_summary}"
        )

    @staticmethod
    def _login(email: str, password: str, proxy: Optional[str] = None) -> Session:
        session = Session()
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        session.headers.update(
            {
                "User-Agent": BROWSER_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "sec-ch-ua": '"Chromium";v="147", "Not.A/Brand";v="8"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            }
        )
        logger.info(f"Using proxy: {'yes' if proxy else 'no'}")

        # Seed the session cookies (PHPSESSID, AWSALB, etc.) by visiting the
        # login page first - the API rejects requests that arrive without them.
        session.get(LOGIN_PAGE)

        response = session.post(
            LOGIN_ENDPOINT,
            json={
                "username": email,
                "password": password,
                "fingerprint": _stable_fingerprint(email),
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://login.aimharder.com",
                "Referer": "https://login.aimharder.com/",
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            },
        )
        cookie_summary = sorted(
            f"{c.name}@{c.domain}" for c in session.cookies
        )
        logger.info(
            f"Login response: status={response.status_code} length={len(response.content)} cookies={cookie_summary}"
        )
        response.raise_for_status()
        # amhrdrauth is the auth cookie - if it's missing, login didn't take.
        if not any(c.name == "amhrdrauth" for c in session.cookies):
            raise BookingFailed(
                f"Login did not set amhrdrauth cookie (body[:200]={response.text[:200]!r})"
            )
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
        response.raise_for_status()
        if not response.text.strip():
            raise BookingFailed(
                f"Classes endpoint returned empty body (status={response.status_code})"
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
                "familyId": family_id if family_id is not None else "",
            },
            headers={
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": box_origin,
                "Referer": f"{box_origin}/schedule",
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            },
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
