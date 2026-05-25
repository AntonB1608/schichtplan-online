from flask import Flask, render_template, request
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("/index.html")

@app.route("/schicht", methods=["POST"])
datum = request.form["datum"]
zeit = request.form["zeit"]
def schicht_eintragen():
    index()

if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5555, debug=True)