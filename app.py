import os
import json
import click
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import Flask, render_template, request, url_for, redirect, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + os.path.join(app.root_path, 'data.db') #设置配置变量，windows中使用sqlite:///
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev'

db = SQLAlchemy(app)

@login_manager.user_loader
def load_user(user_id): #用户加载回调函数
    user = User.query.get(int(user_id))
    return user

#创建数据库模型
class User(db.Model, UserMixin): #用户数据，继承UserMixin类，拥有判断认证状态的属性和方法
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(20))
    password_hash = db.Column(db.String(128)) #密码散列值

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def validate_password(self, password):
        return check_password_hash(self.password_hash, password) #返回布尔值

class Movie(db.Model): #电影数据
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(100))
    year = db.Column(db.String(20))
    info_id = db.Column(db.Integer)

class Watch(db.Model): #观看的电影列表
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(100))

@app.cli.command() #注册为命令
@click.option('--drop', is_flag = True, help = 'Create after drop') #定义可选项
def initdb(drop):
    #设置initdb命令的帮助信息
    """Initialize the database"""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database')

@app.cli.command()
@click.option('--username', prompt=True, help='The username used to login.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password used to login.')
def admin(username, password):
    """Create user."""
    db.create_all()
    user = User.query.first()
    if user is not None:
        click.echo('Updating user...')
        user.username = username
        user.set_password(password) #设置密码
    else:
        click.echo('Creating user...')
        user = User(username=username)
        user.set_password(password) #设置密码
        db.session.add(user)
    db.session.commit() #提交数据库会话
    click.echo('Done.')

@app.context_processor
#模板上下文处理函数，返回的变量自动注入每一个模板的上下文环境
def inject_user(): #函数名随意
    name = User.query.first().username
    return dict(name=name) #需返回字典

def get_movies(): #获取TMDB本周热门信息
    url = 'https://api.themoviedb.org/3/trending/movie/day?api_key=35f8780e7b93cb270f7320f9ba7e0634&language=zh'
    content = requests.get(url).content
    movies_info = json.loads(content)
    for movie in Movie.query.all():
        db.session.delete(movie)
    for result in movies_info['results']:
        movie = Movie(title = result['title'], year = result['release_date'], info_id = result['id'])
        db.session.add(movie)
    db.session.commit() #必不可少

@app.route('/', methods=['GET', 'POST']) #设置函数对应url
def index(): #使用模板生成网页
    if request.method == 'POST': #判断是否是POST请求
        if not current_user.is_authenticated:
            return redirect(url_for('index')) #重定向回主页
        #获取表单数据
        title = request.form.get('title') #传入表单对应输入字段的name值
        #验证数据
        if not title:
            flash('输入错误') #显示错误提示
            return redirect(url_for('index')) #重定向回主页
        #保存表单数据到数据库
        db.session.add(Watch(title=title))
        db.session.commit()
        flash('条目已创建') #显示成功创建的提示
        return redirect(url_for('index')) #重定向回主页
    else:
        get_movies()
    movies = Movie.query.all()
    watchs = Watch.query.all()
    return render_template('index.html', movies = movies, watchs = watchs) #由于使用app.context_processor，无需传入name

@app.route('/watch/edit/<int:watch_id>', methods = ['GET', 'POST'])
@login_required
def edit(watch_id):
    watch = Watch.query.get_or_404(watch_id) #未找到则404
    if request.method == 'POST': #处理编辑表单的提交请求
        title = request.form['title']
        if not title:
            flash('输入错误')
            return redirect(url_for('edit', movie_id=movie_id))#重定向回对应的编辑页面
        watch.title = title #更新标题
        db.session.commit() #提交数据库会话
        flash('条目已更新')
        return redirect(url_for('index')) #重定向回主页
    return render_template('edit.html', watch = watch) # 传入被编辑 的电影记录

@app.route('/watch/delete/<int:watch_id>', methods = ['POST']) #只接受POST请求
@login_required
def delete(watch_id):
    watch = Watch.query.get_or_404(watch_id)
    db.session.delete(watch)
    db.session.commit()
    flash('条目已删除')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('输入错误')
            return redirect(url_for('login'))
        user = User.query.first() #验证用户名和密码是否一致
        if username == user.username and user.validate_password(password):
            login_user(user) #登入用户
            flash('登录成功')
            return redirect(url_for('index')) #重定向到主页
        flash('用户名或密码错误') #如果验证失败，显示错误消息
        return redirect(url_for('login')) #重定向回登录页面
    return render_template('login.html')

@app.route('/logout')
@login_required #用于视图保护
def logout():
    logout_user() #登出用户
    flash('已等出')
    return redirect(url_for('index')) #重定向回首页

@app.errorhandler(404)
def page_not_found(e): #接受异常对象作为参数
    return render_template('404.html'), 404 #返回模板和状态码
