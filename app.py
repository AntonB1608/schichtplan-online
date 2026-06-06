from flask import Flask, render_template, request
from datetime import datetime
 
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/schicht", methods=["POST"])
def schicht_eintragen():
    pfad = "/Users/macbook/Schichtplan_tool/schichten.txt"
    pfadenv = "/Users/macbook/Schichtplan_tool/.env"
    datum = request.form["datum"]
    zeit_anfang = request.form["zeit_anfang"]
    zeit_ende = request.form["zeit_ende"]
    datum_formatiert = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
    frei = request.form.get("frei")
    name = request.form.get("name")
    email = request.form.get("email")
    weckzeit = request.form.get("weckzeit")
    if frei:
        with open(pfad, "a", encoding="utf-8") as f:
            f.write(f"\n{datum_formatiert} frei\n")
    else:
        with open(pfad, "a", encoding="utf-8") as f:
            f.write(f"\n{datum_formatiert} {zeit_anfang}-{zeit_ende}\n")
    return "Schicht eingetragen!"



if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5555, debug=True)
     