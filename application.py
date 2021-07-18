from datetime import datetime
import os
import asyncio

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from sqlparse.tokens import Name
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT companies.symbol, companies.name, SUM(transactions.amount) AS amount, AVG(transactions.price) AS price FROM transactions INNER JOIN companies ON transactions.company_id = companies.id WHERE transactions.user_id = ? GROUP BY companies.symbol;", session.get("user_id"))
    """ rows holds the user portfolio data in this format: SYMBOL | NAME | AMOUNT OF SHARES | AVG PRICE PAID """
    for item in rows:
        """ Adding the current price to each portfolio holding row in the table """
        item['currentPrice'] = lookup(item['symbol'])['price']
    """ Getting the user cash to display at the bottom of the table """
    funds = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
    return render_template("index.html", holdings=rows, cash=funds[0]['cash'])



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if request.form.get("amount").isdigit():
            amount = int(request.form.get("amount"))

            if amount < 1 :
                return render_template("buy.html", message = "Plesse enter a valid amount") 
        else:
                return render_template("buy.html", message = "Plesse enter a valid amount")
        quoteData = lookup(request.form.get("symbol"))
        if quoteData != None:
            """Valid symbol and amount"""
            """Check if user has the funds needed"""
            user_id = session.get("user_id")
            price = int(quoteData["price"])
            neededFunds = price * amount
            funds = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]['cash']
            if neededFunds > funds:
                return render_template("buy.html", message = "Not enough funds available")

            """Check if symbol already in comapnies TABLE"""
            rows = db.execute("SELECT * FROM companies WHERE symbol = ?", quoteData["symbol"])
            if len(rows) == 0:
                """Need to insert it in the companies TABLE"""
                rows = db.execute("INSERT INTO companies (symbol, name) VALUES (?, ?)",quoteData["symbol"], quoteData["name"])
                rows = db.execute("SELECT * FROM companies WHERE symbol = ?", quoteData["symbol"])

            company_id = rows[0]["id"]
            dateTime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            db.execute("INSERT INTO transactions(user_id, company_id, amount, price, datetime) VALUES (?, ?, ?, ?, ?)", user_id, company_id, amount, price, dateTime)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", funds - neededFunds, user_id)
            return render_template("buy.html", message = f"Bought { amount } shares of { quoteData['name'] } ({ quoteData['symbol'] })")
        else:
            return render_template("buy.html", message = "Ticker could not be found")    
        return apology("TODO")

    if request.method == "GET":
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quoteData = lookup(request.form.get("symbol"))
        if quoteData != None:
            return render_template("quote.html", quoteText = f"{quoteData['name']} ({quoteData['symbol']}) stock price is: {usd(quoteData['price'])}")
        else:
            return render_template("quote.html", quoteText = "Could not find this ticker symbol")

    if request.method == "GET":
        return render_template("quote.html", quoteText = "")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        
        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confermation", 403)

        # Ensure password matches password confirmation
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation must match") 

        # Ensure username is not already taken
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("username already taken", 403)

        # Create the user in the DB
        db.execute("INSERT INTO users(username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        # Redirect to log in
        return render_template("login.html")
        
    
    else:
        # User reached route via GET (as by clicking a link or via redirect)
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
