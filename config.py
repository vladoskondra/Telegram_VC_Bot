HEROKU = True  # NOTE Make it false if you're not deploying on heroku.

# NOTE these values are for heroku & Docker.
if HEROKU:
    from os import environ

    from dotenv import load_dotenv

    load_dotenv()  # take environment variables from .env.
    API_ID = int(environ["4889182"])
    API_HASH = environ["38ea074a004c2927bddf31c96f9c03e0"]
    SESSION_STRING = environ[
        "AgB6NePNId_3f65Y1PHoIRiBwCWAtWgd1p7DDs5xD31oATu7Z3uPMlbLaNhSfyCJMDEUxi1bp4ccsKfIkvkdIZm6pa3ooiG5faEqcBYOAzWF66z85tBwt9a_MZ"
    ]  # Check Readme for session
    ARQ_API_KEY = environ["FPHJFJ-ZRCWFB-VEPGPZ-REETOO-ARQ"]
    CHAT_ID = int(environ["-1001137779694"])
    DEFAULT_SERVICE = environ.get("DEFAULT_SERVICE") or "youtube"
    BITRATE = int(environ["BITRATE"])

# NOTE Fill this if you are not deploying on heroku.
if not HEROKU:
    API_ID = 4889182
    API_HASH = "38ea074a004c2927bddf31c96f9c03e0"
    ARQ_API_KEY = "FPHJFJ-ZRCWFB-VEPGPZ-REETOO-ARQ"
    CHAT_ID = -1001137779694
    DEFAULT_SERVICE = "youtube"  # Must be one of "youtube"/"saavn"
    BITRATE = 512 # Must be 512/320

# don't make changes below this line
ARQ_API = "https://thearq.tech"
