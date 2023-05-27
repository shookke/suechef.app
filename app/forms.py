from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import BooleanField, IntegerField, FileField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, NumberRange


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RecipeForm(FlaskForm):
    img = FileField('Image',
        validators=[FileAllowed(['jpg', 'jpeg', 'gif', 'png', 'bmp'], 'Image files (jpg, jpeg, gif, png, bmp) only!')])
    cook_time = IntegerField('Cook Time',
        validators=[DataRequired(), NumberRange(min=1, max=60*24*7)])
    description = StringField('Description', validators=[DataRequired()])
    intro = StringField('Intro', validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired()])
    prep_time = IntegerField('Prep Time',
        validators=[DataRequired(), NumberRange(min=1, max=60*24*7)])
    servings = IntegerField('Servings',
        validators=[DataRequired(), NumberRange(min=1, max=10000)])
    directions = TextAreaField('Directions',validators=[DataRequired()])
    publish = BooleanField('Publish')
    submit = SubmitField('Save')


class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')
