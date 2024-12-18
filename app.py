from app import app

#development
# if __name__ == '__main__':
#     app.jinja_env.auto_reload = True
#     app.config['TEMPLATES_AUTO_RELOAD']=True
#     app.run(debug=True,use_reloader=True)
#     app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 #disable cache

#production
if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=10000)