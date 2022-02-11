import os
import json
import click
import requests
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + os.path.join(app.root_path, 'data.db') #设置配置变量，windows中使用sqlite:///
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#创建数据库模型
class User(db.Model): #用户数据
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(20))

class Movie(db.Model): #电影数据
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(100))
    year = db.Column(db.String(20))
    cover = db.Column(db.String(40))
    info_id = db.Column(db.Integer)

@app.cli.command() #注册为命令
@click.option('--drop', is_flag = True, help='Create after drop') #定义可选项
def initdb(drop):
    #设置initdb命令的帮助信息
    """Initialize the database"""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database')

def get_movies(): #获取TMDB本周热门信息
    url = 'https://api.themoviedb.org/3/trending/movie/day?api_key=35f8780e7b93cb270f7320f9ba7e0634&language=zh'
    content = requests.get(url).content
    movies_info = json.loads(content)
    for movie in Movie.query.all():
        db.session.delete(movie)
    for result in movies_info['results']:
        movie = Movie(title = result['title'], year = result['release_date'], cover = result['poster_path'], info_id = result['id'])
        db.session.add(movie)
    db.session.commit() #必不可少

@app.route('/') #设置函数对应url
def index(): #使用模板生成网页
    get_movies()
    user = User.query.first()
    movies = Movie.query.all()
    return render_template('index.html', name = user.name, movies = movies)
