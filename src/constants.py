LOGIN_PAGE = "https://login.aimharder.com/"
LOGIN_ENDPOINT = "https://login.aimharder.com/api/login"

ERROR_TAG_ID = "loginErrors"


def book_endpoint(box_name):
    return f"https://{box_name}.aimharder.com/api/book"


def classes_endpoint(box_name):
    return f"https://{box_name}.aimharder.com/api/bookings"
