import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # db.execute("SELECT symbol, price, shares FROM transactions GROUP BY symbol")
    # return apology("TODO")
    portfolio_symbols = db.execute("SELECT shares, symbol \
                                    FROM transactions WHERE id = :id", \
                                    id=session["user_id"])

    # create a temporary variable to store TOTAL worth ( cash + share)
    total_cash = 0

    # update each symbol prices and total
    for portfolio_symbol in portfolio_symbols:
        symbol = portfolio_symbol["symbol"]
        shares = portfolio_symbol["shares"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        total_cash += total
        db.execute("UPDATE portfolio SET price=:price, \
                    total=:total WHERE id=:id AND symbol=:symbol", \
                    price=usd(stock["price"]), \
                    total=usd(total), id=session["user_id"], symbol=symbol)

    # update user's cash in portfolio
    updated_cash = db.execute("SELECT cash FROM users \
                               WHERE id=:id", id=session["user_id"])

    # update total cash -> cash + shares worth
    total_cash += updated_cash[0]["cash"]

    # print portfolio in index homepage
    updated_portfolio = db.execute("SELECT * from portfolio \
                                    WHERE id=:id", id=session["user_id"])

    return render_template("index.html", stocks=updated_portfolio, \
                            cash=usd(updated_cash[0]["cash"]), total= usd(total_cash) )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method=="POST":
        symbol= request.form.get("symbol")
        shares = (int)(request.form.get("shares"))
        if not symbol or not shares:
            return apology("Invalid input",402)
        cash = db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])[0]["cash"]
        row = lookup(symbol)
        money = shares*row["price"]
        price = row["price"]

        if money>cash:
            return apology("Cash is insufficient",402)
        cashleft = cash-money
        db.execute("UPDATE users SET cash = ? WHERE id= ? ",cashleft,session["user_id"])
        k = db.execute("SELECT shares,price FROM transactions WHERE symbol = ?",symbol)
        if k!=None:
            quantearlier = k[0]["shares"]
            earlyprice = k[0]["price"]
        price = (price*shares+earlyprice*quantearlier)/(shares+quantearlier)

        newquant = quantearlier+shares
        result = db.execute("SELECT symbol FROM transactions")

        if result== None:
            db.execute("INSERT INTO transactions (shares, symbol, price, user_id) VALUES (?,?,?,?)",newquant,symbol,price,session["user_id"])
            db.execute("INSERT into portfolio VALUES price=:price, \
                    total=:total shares=:shares name=:name WHERE id=:id AND symbol=:symbol", \
                    price=usd(price), \
                    total=usd(newquant*price), id=session["user_id"], symbol=symbol, shares=newquant, name=lookup(symbol)["name"])
        else:
            db.execute("UPDATE transactions SET shares=?, symbol= ?, price=?,user_id =?", newquant,symbol,price,session["user_id"])
            db.execute("UPDATE portfolio SET price=:price, \
                    total=:total WHERE id=:id AND symbol=:symbol", \
                    price=usd(price), \
                    total=usd(price*newquant), id=session["user_id"], symbol=symbol)
        flash("Bought!!")
        return redirect("/buy")
    else:
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
    if request.method== "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("No symbol provided",403)
        response = lookup(symbol)
        return render_template("quoted.html",response=response)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 0 :
            return apology("Username already exists", 403)
        if not confirmation or password != confirmation:
            return apology("Invalid password or passwords don't match", 403)
        db.execute("INSERT into users (username,hash) VALUES(?,?)",username,generate_password_hash(password))
    else :
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")
