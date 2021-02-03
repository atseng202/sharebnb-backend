import os

from flask import Flask, request, jsonify
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError
# from flask_jwt import JWT, jwt_required, current_identity
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity, get_jwt_claims
)

from forms import (
    UserSignUpForm, UserLoginForm, ListingForm, ListingSearchForm
)
from models import db, connect_db, User, Listing

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgres:///sharebnb'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', "shhhhh!")
jwt = JWTManager(app)

app.config['WTF_CSRF_ENABLED'] = False

toolbar = DebugToolbarExtension(app)

connect_db(app)

##############################################################################
# JWT

# Create a function that will be called whenever create_access_token
# is used. It will take whatever object is passed into the
# create_access_token method, and lets us define what custom claims
# should be added to the access token.
@jwt.user_claims_loader
def add_claims_to_access_token(user):
    return {
        'username': user.username,
        'is_admin': user.is_admin,
        }

# Create a function that will be called whenever create_access_token
# is used. It will take whatever object is passed into the
# create_access_token method, and lets us define what the identity
# of the access token should be.
@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.username

# test of JWT for protected routes
@app.route('/protected', methods=['GET'])
@jwt_required
def protected():
    ret = {
        'username': get_jwt_identity(),
        'is_admin': get_jwt_claims()['is_admin']
    }
    return jsonify(ret), 200

##############################################################################
# User signup/login/logout

# @app.before_request
# def add_user_to_g():
#     """If we're logged in, add curr user to Flask global."""

    # if CURR_USER_KEY in session:
    #     g.user = User.query.get(session[CURR_USER_KEY])
    # if request.header.get("authorization", None):
        # JWT verify the Bearer token
    #     print("set g.user")
    # else:
    #     g.user = None


def do_login(user):
    """Log in user by returning token for future auth checking.
    """

    access_token = create_access_token(identity=user)
    return (jsonify(token=access_token), 200)


@app.route('/signup', methods=["POST"])
def signup():
    """Handle user signup.
    Create new user and add to DB. Returns a JWT token which can be used to
    authenticate further requests,  { status_code: 201, token }

    If form not valid, returns JSON error messages like,  
    { status_code: 404, errors }
    """

    user_data = request.json.get("user")
    form = UserSignUpForm(data=user_data)

    if form.validate():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data,
                location=form.location.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()
            return do_login(user)
        except IntegrityError as e:
            print(e)
            errors = ["Username already taken"]
            return (jsonify(errors=errors), 400)
    else:
        errors = []
        for field in form:
            for error in field.errors:
                errors.append(error)
        return(jsonify(errors=errors), 400)


@app.route('/login', methods=["POST"])
def login():
    """Handle user login.
    Validates user credentials with form. Returns JWT token if authenticated,
    otherwise, returns error messages
    """

    user_data = request.json.get("user")
    form = UserLoginForm(data=user_data)

    if form.validate():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            return do_login(user)

        return (jsonify(errors=["Invalid credentials."]), 401)
    else:
        errors = []
        for field in form:
            for error in field.errors:
                errors.append(error)
        return(jsonify(errors=errors), 400)


##############################################################################
# General user routes:

@app.route('/users/<username>')
def user_show(username):
    """Show user profile."""

    user = User.query.get_or_404(username)
    # snagging messages in order from the database;
    # user.messages won't be in order by default
    # messages = (Message
    #             .query
    #             .filter(Message.user_id == user_id)
    #             .order_by(Message.timestamp.desc())
    #             .limit(100)
    #             .all())
    user_obj = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "image_url": user.image_url,
        "email": user.email,
        "bio": user.bio,
        "location": user.location
    }
    return (jsonify(user=user_obj), 200)


# NOTE: No edit or delete user routes at the moment, will add if needed

##############################################################################
# TODO: Add Message routes after auth and listing routes work
# Messages routes:

# @app.route('/messages/<:from_username>/<:to_username>', methods=["GET"])
# def messages_list():

# @app.route('/messages/new', methods=["GET", "POST"])
# def message_add():


##############################################################################
# General listing routes:

@app.route('/listings')
@jwt_required
def listings_list():
    """ Show listings based on query parameters
    Auth required: none
    """

    def convert_inputs(data):
        output = {}
        max_price = data.get("max_price", None)
        longitude = data.get("longitude", None)
        latitude = data.get("latitude", None)
        beds = data.get("beds", None)
        bathrooms = data.get("bathrooms", None)

        if max_price:
            output["max_price"] = int(max_price)

        if longitude:
            output["longitude"] = float(longitude)

        if latitude:
            output["latitude"] = float(latitude)

        if beds:
            output["beds"] = int(beds.split(".")[0])

        if bathrooms:
            output["bathrooms"] = int(bathrooms.split(".")[0])

        return output

    inputs = convert_inputs(request.args)
    form = ListingSearchForm(data=inputs)
    if form.validate():
        listings = Listing.find_all(inputs).all()
        print("Listings: ", listings, "type :", type(listings))
        serialized = [listing.serialize(isDetailed=False) for listing in listings]
        return (jsonify(listings=serialized), 200)
    else:
        return (jsonify(errors=["Bad request"]), 400)


@app.route('/listings/<int:listing_id>')
@jwt_required
def listing_show(listing_id):
    """ Show a listing

    Auth required: none
    """

    listing = Listing.query.get_or_404(listing_id)
    if not listing:
        return (jsonify(errors=["Listing does not exist"]), 404)
    else:
        return (jsonify(listing=listing.serialize(isDetailed=True)), 200)


@app.route('/listings', methods=["POST"])
@jwt_required
def listing_create():
    """
    Create a new listing.

    Auth required: admin or logged in user
    """
    listing_data = request.json.get("listing")
    form = ListingForm(data=listing_data)

    if form.validate():
        listing = Listing.create(
            title=form.title.data,
            description=form.description.data,
            photo=form.photo.data or Listing.photo.default.arg,
            price=form.price.data,
            longitude=form.longitude.data,
            latitude=form.latitude.data,
            beds=form.beds.data,
            rooms=form.rooms.data,
            bathrooms=form.bathrooms.data,
            created_by=form.created_by.data
        )
        db.session.commit()
        # TODO: reevaluate error with a try and except later
        return (jsonify(listing=listing.serialize(isDetailed=True)), 201)
    else:
        errors = []
        for field in form:
            for error in field.errors:
                errors.append(error)
        return(jsonify(errors=errors), 400)

# TODO: 
# @app.route('/listings/:id', methods=["PATCH"])
# def listing_edit():

# @app.route('/listings/delete', methods=["POST"])


##############################################################################
# after each request

@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response
