# GoTaxi — Flask demo MVP

A beginner-friendly **educational prototype**, built with OOP and basic Flask. Uses the photo supplied by the project creator.

## Features
- Splash screen with GoTaxi branding; optional **user-supplied** `static/audio/intro.mp3` played after clicking a button.
- Taxi, parcel delivery, cargo, food-delivery demo, Sprinter and bus requests.
- Fixed time-of-day fare tiers; manually entered distance in km.
- Promo `GO10`, bonus balance, order history, order ratings.
- Mock restaurants and cinema listing; **not live nearby results**.
- Mock payment labels only. **Never enter real card information.**

## Install and run (Windows / VS Code)

```powershell
cd GoTaxi
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000/**.

If PowerShell blocks activation, you can use `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe app.py` instead.

## Source files
- `app.py`: Flask routes.
- `models.py`: `Customer`, `ServiceOrder`, `FarePolicy`, `GoTaxiSystem`.
- `templates/`: Jinja HTML pages.
- `static/css/style.css`: UI.
- `static/images/gotaxi_splash.webp`: uploaded user photo.
- `static/audio/`: optional licensed `intro.mp3`; **not bundled**.

## Important limitations

This is **not** a production booking platform. There are no real drivers, geolocation, route calculations, live restaurant data, accounts/authentication, actual payments, or card vaulting. The app is for **local demo use only**, with a shared demo customer and data stored only in RAM. After server restart, orders and bonus changes reset. Run in debug mode **locally only**, not on a public server. Do not use real personal/payment information.

If you already have your own backend code, you can copy its OOP logic into `models.py` and adapt the routes in `app.py`.
