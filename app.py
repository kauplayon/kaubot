from flask import Flask, jsonify, render_template

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "online", "application": "NEXUS", "version": "1.0.0"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
