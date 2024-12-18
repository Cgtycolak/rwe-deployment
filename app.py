from app import app

if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD']=True
    app.run(debug=True,use_reloader=True)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 #disable cache

