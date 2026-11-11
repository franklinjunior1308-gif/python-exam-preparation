"""GoTaxi Flask educational MVP. Demo only, no production payment or ride dispatch."""
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from models import GoTaxiSystem, SERVICES, RESTAURANTS

app = Flask(__name__)
app.config["SECRET_KEY"] = "gotaxi-development-only-change-me"
# IMPORTANT: One in-memory demo account shared by visitors. Run locally only.
system = GoTaxiSystem()


@app.context_processor
def common():
    return {"customer": system.customer, "services": SERVICES}


@app.get("/")
def splash():
    has_audio = (Path(app.static_folder) / "audio" / "intro.mp3").exists()
    return render_template("splash.html", has_audio=has_audio)


@app.get("/home")
def home():
    return render_template("home.html", fares=system.fares,
                           restaurants=RESTAURANTS, current_hour=datetime.now().hour)


@app.route("/book/<service>", methods=["GET", "POST"])
def book(service):
    if service not in SERVICES:
        abort(404)
    hour = datetime.now().hour
    if request.method == "POST":
        try:
            distance = float(request.form.get("distance_km", "0"))
            passengers = int(request.form.get("passengers", "1"))
            use_bonuses = int(request.form.get("bonuses", "0"))
            order = system.book(
                service, request.form.get("origin", ""), request.form.get("destination", ""),
                distance, passengers, request.form.get("promo", ""), use_bonuses,
            )
        except (ValueError, OverflowError) as error:
            flash(str(error), "error")
        else:
            flash(f"Демо-заказ {order.order_id} создан. Оплата не списывалась.", "success")
            return redirect(url_for("history"))
    return render_template("book.html", service=service, fare=system.fares, hour=hour)


@app.get("/history")
def history():
    return render_template("history.html", orders=list(reversed(list(system.orders.values()))))


@app.post("/orders/<order_id>/complete")
def complete(order_id):
    try:
        system.complete(order_id)
        flash("Демо-заказ завершён. Бонусы начислены.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("history"))


@app.post("/orders/<order_id>/rate")
def rate(order_id):
    try:
        system.rate(order_id, int(request.form.get("rating", "0")))
        flash("Спасибо за оценку!", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("history"))


@app.route("/wallet", methods=["GET", "POST"])
def wallet():
    if request.method == "POST":
        try:
            system.customer.add_mock_card(request.form.get("card_label", ""))
            flash("Демо-способ оплаты добавлен. Данные карты не запрашивались.", "success")
            return redirect(url_for("wallet"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("wallet.html")


@app.get("/places")
def places():
    return render_template("places.html", restaurants=RESTAURANTS)


if __name__ == "__main__":
    app.run(debug=True)
