import logging
import os
from app import app, db
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash
from sqlalchemy.sql.expression import func
from slugify import slugify
from forms import LoginForm, RecipeForm, RegisterForm
from models import User, Setting, Category, Tag, UserRecipe, Recipe, Ingredient, \
    RecipeIngredient, Meal
from datetime import date, timedelta
from collections import defaultdict

LOGGER = logging.getLogger(__name__)

MEDIA_PATH = os.path.join(os.path.dirname(app.instance_path), app.config['UPLOAD_FOLDER'])

SETTING_DEFAULTS = {
    "allow_user_registration" :  True,
    "default_category"        :  ["main"],
    "default_servings"        :  2,
    "default_duration"        :  ["0-15"],
    "default_language"        :  "en-us",
    "grocery_day"             :  "sat",
}


@app.route('/')
def home():
    recipes = Recipe.query.order_by(func.random()).limit(4).all()
    meals = Meal.query.filter(Meal.day >= date.today()) \
                      .order_by(Meal.day).all()

    days = defaultdict(list)
    for meal in meals:
        days[str(meal.day)].append(meal)

    return render_template('home.html', recipes=recipes, days=days)


@app.route('/scheduler')
@login_required
def scheduler():
    return render_template('scheduler.html')


@app.route('/recipes')
@login_required
def recipes():
    filter = dict()
    filter['query'] = request.args.get('query')
    filter['categories'] = request.args.getlist('category')
    filter['tags'] = request.args.getlist('tag')

    day = request.args.get('day')

    query = Recipe.query.order_by(func.random())
    if filter['query']:
        query = query.filter(Recipe.name.ilike('%{}%'.format(filter['query'])))
    if filter['categories']:
        query = query.filter(Recipe.category.has(
                    Category.name.in_(filter['categories'])
                ))
    if filter['tags']:
        query = query.filter(Recipe.tags.any(
                    Tag.name.in_(filter['tags'])
                ))

    recipes = query.all()
    categories = Category.query.all()
    tags = Tag.query.all()

    return render_template('recipes.html',
                           recipes=recipes, categories=categories, tags=tags,
                           filter=filter, day=day)


@app.route('/recipes/new', methods=["GET", "POST"])
@login_required
def recipe_new():
    """Create a new recipe."""
    user = User.query.filter_by(id=current_user.get_id()).first()
    form = RecipeForm()
    form.category.choices = [(cat.id, cat.name) for cat in Category.query.order_by('name')]
    LOGGER.debug("New recipe form.")
    if form.validate_on_submit():            
        LOGGER.debug("Validating new recipe form.")
        recipe = Recipe(
            author = current_user.name,
            cook_time = form.cook_time.data,
            description = form.description.data,
            name = form.name.data,
            prep_time = form.prep_time.data,
            servings = form.servings.data,
            intro = form.intro.data,
            directions = form.directions.data,
            published = form.publish.data,
        )
        recipe.category = Category.query.filter_by(id=form.category.data).first()
        user.recipes.append(UserRecipe(recipe,None, 0))
        session = db.session
        session.add(recipe)
        session.commit()
        file = form.img.data
        if file:
            filename = file.filename.split('.')
            filename = str(recipe.id) + "." + filename[1]
            file.save(os.path.join(MEDIA_PATH, filename))
            recipe.img = filename
        else:
            recipe.img = 'default.jpg'
        session.commit()
        LOGGER.info("Created recipe %s", form.name.data)
        return redirect(url_for('recipe', id=recipe.id))
    else:
        for error in form.errors:
            LOGGER.debug("Error: %s", error)


    return render_template('recipe_new.html', form=form)


@app.route('/recipes/search')
@login_required
def search():
    query = request.args.get('q')
    result = {'results': []}

    if query:
        clauses = [Recipe.name.ilike('%{}%'.format(k)) for k in query.split()]
        recipes = Recipe.query.filter(*clauses).all()
        for recipe in recipes:
            result['results'].append({
                'title': recipe.name,
                'description': recipe.intro,
                'image': '/static/food/{}'.format(recipe.img),
                'link': url_for('recipe', id=recipe.id, name=slugify(recipe.name))
            })

    return jsonify(result)


@app.route('/recipes/<int:id>')
@app.route('/recipes/<int:id>/<name>')
@login_required
def recipe(id, name=None):
    recipe = Recipe.query.get_or_404(id)
    user_recipe = UserRecipe.query.filter_by(recipe_id=id).filter_by(author_id=current_user.get_id()).first()
    slug = slugify(recipe.name)

    if slug != name:
        return redirect(url_for('recipe', id=recipe.id, name=slug))

    return render_template('recipe.html', recipe=recipe, user_recipe=user_recipe)


@app.route('/recipes/<int:id>', methods=['PATCH'])
@login_required
def recipe_update(id):
    user_recipe = UserRecipe.query.filter_by(recipe_id=id).filter_by(author_id=current_user.get_id()).first()
    recipe = Recipe.query.get_or_404(id)
    rating = request.json.get('rating')
    if user_recipe:
        if user_recipe.rating == 0:
            recipe.rating_count += 1
        user_recipe.rating = rating
        recipe.rating = (recipe.rating + rating) / float(recipe.rating_count)
    if not user_recipe:
        user_recipe = UserRecipe(recipe)
        user_recipe.rating = rating
        recipe.rating_count += 1
        recipe.calc_rating(rating)
    db.session.commit()
    return '', 204

@app.route('/recipes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def recipe_edit(id):
    recipe = Recipe.query.get_or_404(id)
    form = RecipeForm()
    form.category.choices = [(cat.id, cat.name) for cat in Category.query.order_by('name')]
    if form.validate_on_submit():
        file = form.img.data
        if file:
            filename = file.filename.split('.')
            filename = str(recipe.id) + "." + filename[1]
            file.save(os.path.join(MEDIA_PATH, filename))
            recipe.img = filename
        recipe.name = form.name.data
        recipe.prep_time = form.prep_time.data
        recipe.cook_time = form.cook_time.data
        recipe.servings = form.servings.data
        recipe.intro = form.intro.data
        recipe.description = form.description.data
        recipe.directions = form.directions.data
        recipe.published = form.publish.data
        
        recipe.category = Category.query.filter_by(id=form.category.data).first()
        db.session.commit()
        LOGGER.info("Changes to recipe %s have been saved", form.name.data)
        return redirect(url_for('recipe', id=recipe.id))
    else:
        for error in form.errors:
            LOGGER.debug("Error: %s", error)
    
    return render_template('recipe_edit.html', recipe=recipe, form=form)


@app.route('/groceries')
@login_required
def groceries():
    return render_template('groceries.html')


@app.route('/pantry')
@login_required
def pantry():
    return render_template('pantry.html')

@app.route('/profile', methods=['GET', 'PATCH'])
@login_required
def profile():
    user = current_user
    if request.method == 'PATCH':
        if request.json.get('name'):
            user.name = request.json.get('name')
        if request.json.get('password'):
            user.set_password(request.json.get('password'))
        if request.json.get('email'):
            user.email = request.json.get('email')
        settings = request.json.get('settings')
        LOGGER.debug("These are the recieved settings: %s", settings)
        if settings:
            user.settings = []
            for setting in settings:
                LOGGER.debug("The individual setting: %s", setting)
                try:
                    k = str(next(iter(setting)))
                    LOGGER.debug("Name: %s", k)
                    v = setting[k]
                    LOGGER.debug("Value: %s", v)
                    if v:
                        setting = Setting.query.filter_by(name=k).filter_by(value=v).first()
                        if setting is None:
                            setting = Setting(k, v)
                        LOGGER.debug("Setting Object: %s", setting)
                    else:
                        LOGGER.debug("Skipping due to no value")
                        continue
                except:
                    LOGGER.error("Setting query hit an exception!")
                try:
                    user.settings.append(setting)
                except:
                    LOGGER.error("Could not append to user settings")
        db.session.commit()
        return 'Settings saved', 204
    return render_template('profile.html', user=user)
    
@app.route('/settings')
@login_required
def settings():
    user = current_user

    count = {
      'recipes': Recipe.query.count(),
      'ingredients': Ingredient.query.count(),
      'tags': Tag.query.count(),
      'categories': Category.query.count()
    }

    # Query all settings and create a dict with the setting's name as key
    settings = dict()
    for s in user.settings:
        name = s.name
        if s.name in settings.keys():
            if not isinstance(settings[name], str):
                settings[name].append(s.value)
            else:
                settings[name] = [settings[name], s.value]
            LOGGER.debug("Setting list: %s", settings[name])
        else:
            settings[name] = s.value

    settings['available_languages'] = app.config['LANGUAGES']
    for k, v in SETTING_DEFAULTS.items():
        if k in settings:
            continue
        settings[k] = v

    return render_template('settings.html',
                           user=user, count=count, settings=settings)


@app.route('/settings/ingredients')
@login_required
def ingredients():
    ingredients = Ingredient.query.all()

    return render_template('ingredients.html', ingredients=ingredients)


@app.route('/settings/tags')
@login_required
def tags():
    tags = Tag.query.all()

    return render_template('tags.html', tags=tags)


@app.route('/settings/categories')
@login_required
def categories():
    categories = Category.query.all()

    return render_template('categories.html', categories=categories)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(name=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))

        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('home'))

    return render_template('login.html', form=form, register_link=url_for("register"))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(name=form.username.data).first()
        if user:
            LOGGER.info("Username '%s' already taken.", form.username.data)
            flash('Username already taken, please choose another')
            return redirect(url_for('register'))

        user = User(
            email=form.email.data,
            name=form.username.data,
            password=generate_password_hash(form.password.data))

        session = db.session
        session.add(user)
        session.commit()
        LOGGER.info("Created user %s", form.username.data)

        login_user(user, remember=False)
        return redirect(url_for('home'))


    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/generator', methods=['GET', 'POST'])
def generator():
    # Clear up database first
    User.query.delete()
    Setting.query.delete()
    Category.query.delete()
    Tag.query.delete()
    Recipe.query.delete()
    Ingredient.query.delete()
    RecipeIngredient.query.delete()
    Meal.query.delete()

    grocery_day             = Setting('grocery_day', 'sat')
    default_servings        = Setting('default_servings', '2')
    allow_user_registration = Setting('allow_user_registration', 'true')
    default_language        = Setting('default_language', 'en')

    starter   = Category('Starter')
    main      = Category('Main')
    side_dish = Category('Side dish')
    desert    = Category('Desert')
    breakfast = Category('Breakfast')
    lunch     = Category('Lunch')

    vegetarian = Tag('Vegetarian')
    indian     = Tag('Indian')
    italian    = Tag('Italian')
    moroccan   = Tag('Moroccan')
    lactose    = Tag('Lactose free')

    recipe1 = Recipe(
        name='Fish curry', author="SueChef", servings=4, prep_time=15, cook_time=30,
        category=main, intro='A delicious but simple curry', description="""
            a description.""",
        directions="""Wash and cook the rice.\n\nStart with oil and fry the
            paste for 5 minutes. Add the fish and coconut milk. Poach fish until
            tender. Finalize with coriander.""")

    rice = Ingredient('Rice', 'g')
    paste = Ingredient('Curry paste', 'ts')
    fish = Ingredient('White fish', 'g')
    coconut = Ingredient('Coconut milk', 'ml')
    coriander = Ingredient('Coriander', 'g')

    recipe1.ingredients.append(RecipeIngredient(rice, 320))
    recipe1.ingredients.append(RecipeIngredient(paste, 3, 0.75))
    recipe1.ingredients.append(RecipeIngredient(fish, 400))
    recipe1.ingredients.append(RecipeIngredient(coconut, 150))
    recipe1.ingredients.append(RecipeIngredient(coriander, 20))

    recipe2 = Recipe(name='Pasta something', author="SueChef", servings=4, prep_time=20, cook_time=15, category=main,
        intro='Quick pasta for a working day meal', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe3 = Recipe(name='Weekend tajine', author="SueChef", servings=4, prep_time=30, cook_time=60, category=main,
        intro='Something truly the waiting for during a weekend', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe4 = Recipe(name='Fish curry', author="SueChef", servings=4, prep_time=15, cook_time=30, category=main,
        intro='A delicious but simple curry', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe5 = Recipe(name='Pasta something', author="SueChef", servings=4, prep_time=20, cook_time=15, category=main,
        intro='Quick pasta for a working day meal', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe6 = Recipe(name='Weekend tajine', author="SueChef", servings=4, prep_time=30, cook_time=60, category=main,
        intro='Something truly the waiting for during a weekend', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe7 = Recipe(name='Fish curry', author="SueChef", servings=4, prep_time=15, cook_time=30, category=main,
        intro='A delicious but simple curry', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe8 = Recipe(name='Pasta something', author="SueChef", servings=4, prep_time=20, cook_time=15, category=main,
        intro='Quick pasta for a working day meal', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe9 = Recipe(name='Weekend tajine', author="SueChef", servings=4, prep_time=30, cook_time=60, category=main,
        intro='Something truly the waiting for during a weekend', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe10 = Recipe(name='Fish curry', author="SueChef", servings=4, prep_time=15, cook_time=30, category=main,
        intro='A delicious but simple curry', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    recipe11 = Recipe(name='Zaalouk', author="SueChef", servings=4, prep_time=15, cook_time=0, category=side_dish,
        intro='Moroccan Vegetable side dish', description="""
            a description.""",
        directions="Cut the eggplants to cubes, if you like you can peel the eggplant not completely you leave some skin on them for the dark look.\n\nCut the tomato to fine slices")

    recipe12 = Recipe(name='A very long title with multiple words', author="SueChef", servings=4, prep_time=30, cook_time=60, category=main,
        intro='Something truly the waiting for during a weekend', description="""
            a description.""",
        directions="Start with bla bla and then\nDo some more steps\n\nEnjoy!")

    session = db.session
    session.add(grocery_day)
    session.add(default_servings)
    session.add(allow_user_registration)
    session.add(default_language)
    session.add(starter)
    session.add(main)
    session.add(side_dish)
    session.add(desert)
    session.add(breakfast)
    session.add(lunch)
    session.add(vegetarian)
    session.add(indian)
    session.add(italian)
    session.add(moroccan)
    session.add(lactose)
    session.add(recipe1)
    session.add(recipe2)
    session.add(recipe3)
    session.add(recipe4)
    session.add(recipe5)
    session.add(recipe6)
    session.add(recipe7)
    session.add(recipe8)
    session.add(recipe9)
    session.add(recipe10)
    session.add(recipe11)
    session.add(recipe12)

    session.commit()

    recipe1.tags.append(indian)
    recipe1.tags.append(lactose)

    recipe11.tags.append(moroccan)
    
    recipe1.img = 'default.jpg'
    recipe2.img = 'default.jpg'
    recipe3.img = 'default.jpg'
    recipe4.img = 'default.jpg'
    recipe5.img = 'default.jpg'
    recipe6.img = 'default.jpg'
    recipe7.img = 'default.jpg'
    recipe8.img = 'default.jpg'
    recipe9.img = 'default.jpg'
    recipe10.img = 'default.jpg'
    recipe11.img = 'default.jpg'
    recipe12.img = 'default.jpg'

    session.commit()

    today = Meal(date.today(), recipe1)
    tomorrow = Meal(date.today() + timedelta(days=1), recipe2)
    tomorrow1 = Meal(date.today() + timedelta(days=1), name='Green salad', note='Use rocket salad from yesterday')
    tomorrow2 = Meal(date.today() + timedelta(days=2),
                     name='Rösti with lamb and red cabbage',
                     note='Rösti from freezer, check lamb first!')
    tomorrow3 = Meal(date.today() + timedelta(days=3), recipe3, servings=4)
    tomorrow4 = Meal(date.today() + timedelta(days=4), name='Chicken biryani')
    tomorrow5 = Meal(date.today() + timedelta(days=5), recipe9)
    tomorrow6 = Meal(date.today() + timedelta(days=5), recipe11)

    session.add(today)
    session.add(tomorrow)
    session.add(tomorrow1)
    session.add(tomorrow2)
    session.add(tomorrow3)
    session.add(tomorrow4)
    session.add(tomorrow5)
    session.add(tomorrow6)

    session.commit()

    return redirect(url_for('home'))
