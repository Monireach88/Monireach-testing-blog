from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from typing import Callable
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
import os
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from sqlalchemy.orm import relationship
from datetime import date
from functools import wraps
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
# unlike sqlite which is built-in in pycharm, make sure postgreSQL's package (psycopg2-binary) has been installed



# make sure the Column, String, Integer ... of SQLAlchemy will not be marked yellow
class MySQLAlchemy(SQLAlchemy):
    Column: Callable
    String: Callable
    Integer: Callable
    Text: Callable
    ForeignKey: Callable


# initialize the Flask app
app = Flask(__name__)
# initialize flask_bootstrap
Bootstrap(app)
# # initialize flask_sqlalchemy using sqlite
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
# initialize flask_sqlalchemy using postgreSQL which can work with Heroku.

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")  # the DATABASE_URL can
# be obtained from Heroku > Setting > Config Vars; it's also specified that iff the DATABASE_URL is not provided,
# run locally
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# # configure a Secret key to use flask form using sqlite
# app.config['SECRET_KEY'] = "kadjsfioawu39r89gjv9vz#9t8af"
# configure a Secret Key to use flask form with postgreSQL
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
db = MySQLAlchemy(app)
# initialize CKEditor
ckeditor = CKEditor(app)
app.config['CKEDITOR_PKG_TYPE'] = 'standard-all'
# initialize flask_login
login_manager = LoginManager()
login_manager.init_app(app)
# initialize flask_gravatar
gravatar = Gravatar(
    app,
    size=100,
    rating='g',
    default='retro',
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None
)


# to load a user, create a load_user function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create admin_only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        else:
            return f(*args, **kwargs)
    return decorated_function


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)

    # Parent relationship with BlogPost
    posts = relationship("BlogPost", back_populates="author")

    # Parent relationship with Comment
    comments = relationship("Comment", back_populates="comment_author")

    # This function will remove the yellow highlight (of Unexpected argument, due to the UserMixin) when we create a
    # User object later on
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Child relationship with User
    # Create Foreign Key, "users.id" the users refers to the table name of the User
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Create reference to the User object, the "posts" refers to the posts property of the User class
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Parent relationship with Comment
    comments = relationship("Comment", back_populates="parent_post")


# CONFIGURE THE COMMENT TABLE
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)

    # Child relationship with User
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")

    # Child relationship with BlogPost
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")

    text = db.Column(db.Text, nullable=False)


if not os.path.isfile('sqlite:///blog.db'):
    db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hash_and_salted_password = generate_password_hash(
            password=form.password.data,
            method='pbkdf2:sha256',
            salt_length=8,
        )
        new_user = User(
            email=form.email.data,
            password=hash_and_salted_password,
            name=form.name.data.title(),
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # check if user exists
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Invalid Password! Please try again.")
        else:
            flash("No user found! Please try again.")

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()

    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=comment_form.comment_text.data,
                comment_author=current_user,
                parent_post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("You need to login or register to comment.")

    return render_template("post.html", post=requested_post, form=comment_form, date=date.today().strftime("%B %d, %Y"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["POST", "GET"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            author=current_user,
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user.name
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

