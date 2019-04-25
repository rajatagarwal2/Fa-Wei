from flask import Flask, render_template, request, redirect, url_for
from flask_mongoengine import MongoEngine, Document
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import Email, Length, InputRequired
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import pymongo
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import math


def create_app():
    app = Flask(__name__)

    app.config['MONGODB_SETTINGS'] = {
        'db': 'test_app_mongo',
        'host': 'mongodb://localhost:27017/test_app_mongo'
    }

    mongodb = MongoClient('localhost', 27017).test_app_mongo

    db = MongoEngine(app)
    app.config['SECRET_KEY'] = os.urandom(12)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'






    class User(UserMixin, db.Document):
        meta = {'collection': 'users'}
        email = db.StringField(max_length=30)
        password = db.StringField()
        name = db.StringField(max_length=30)
        user_type = db.StringField(max_length=30)
        login = db.StringField(max_length=30)
        mac_id = db.StringField(max_length=30)
        location = db.StringField()


    @login_manager.user_loader
    def load_user(user_id):
        return User.objects(pk=user_id).first()

    class RegForm(FlaskForm):
        email = StringField('email',  validators=[InputRequired(), Email(message='Invalid email'), Length(max=30)])
        password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=20)])
        name = StringField('name')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        form = RegForm()
        if request.method == 'POST':
            user_type = request.form['user_type']
            if form.validate():
                existing_user = User.objects(email=form.email.data).first()
                if existing_user is None:
                    hashpass = generate_password_hash(form.password.data, method='sha256')
                    hey = User(form.email.data,hashpass,form.name.data,user_type).save()
                    login_user(hey)
                    return redirect(url_for('dashboard'))
        return render_template('register.html', form=form)


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated == True:
            return redirect(url_for('dashboard'))
        form = RegForm()
        if request.method == 'POST':
            if form.validate():
                check_user = User.objects(email=form.email.data).first()
                if check_user:
                    if check_password_hash(check_user['password'], form.password.data):
                        login_user(check_user)
                        return redirect(url_for('dashboard'))
        return render_template('login.html', form=form)


    @app.route('/')
    def home():
        return render_template('home.html')


    # @app.route('/add_painting', methods=['POST'])
    # @login_required
    # def add_painting():
    #     if request.method == "POST":
    #         painting_features = {
    #             "title": request.form['title'],
    #             "artist": request.form['artist'],
    #             "category": request.form['category'],
    #             "year": request.form['year'],
    #             "country": request.form['country'],
    #             "type_art": request.form['type_art'],
    #         }

    #         mongodb.paintings.insert(painting_features)

    #     return render_template('dashboard.html', name=current_user.name, user_type=current_user.user_type)

    @app.route('/dashboard', methods=['GET', 'POST'])
    @login_required
    def dashboard():

        if request.method == "POST":
            if current_user.user_type == 'Management':
                painting_features = {
                    "title": request.form['title'],
                    "artist": request.form['artist'],
                    "category": request.form['category'],
                    "year": request.form['year'],
                    "country": request.form['country'],
                    "type_art": request.form['type_art'],
                }
                mongodb.paintings.insert(painting_features)


                # Code for recommendation starts here
                art_data_file = pd.read_csv('static/art_features.csv')

                art_features = art_data_file.drop(['Link','Title', 'Latitude','Longitude','Country'], axis=1)

                painting_to_be_installed = pd.DataFrame([[request.form['category'], request.form['artist'], request.form['type_art'], 
                    request.form['year']]], columns=['Category', 'Creator ', 'Type', 'Year'])

                painting_to_be_installed = painting_to_be_installed.iloc[0]



                from sklearn import preprocessing

                category = preprocessing.LabelEncoder()
                category.fit(art_features['Category'])
                art_features['Category'] = category.transform(art_features['Category'])

                creator = preprocessing.LabelEncoder()
                creator.fit(art_features['Creator '])
                art_features['Creator '] = creator.transform(art_features['Creator '])

                art_type = preprocessing.LabelEncoder()
                art_type.fit(art_features['Type'])
                art_features['Type'] = art_type.transform(art_features['Type'])


                new_painting = []
                new_painting.append(category.transform([painting_to_be_installed['Category']])[0])
                new_painting.append(creator.transform([painting_to_be_installed['Creator ']])[0])
                new_painting.append(painting_to_be_installed['Year'])
                new_painting.append(art_type.transform([painting_to_be_installed['Type']])[0])


                from sklearn.metrics import jaccard_similarity_score
                sim_scores = []
                min_sim_score = 0
                for index, painting in art_features.iterrows():
                    sim_scores.append(jaccard_similarity_score(painting, new_painting))


                top_20_sim_paintings_index = sorted(range(len(sim_scores)), key=lambda k: sim_scores[k], reverse = True)[:20]


                top_20_paintings = art_data_file.iloc[top_20_sim_paintings_index]
                top_20_paintings_lat = top_20_paintings['Latitude']
                top_20_paintings_long = top_20_paintings['Longitude']


                time_spent_per_lat_long = pd.read_csv('static/one_day.csv')


                time_spent = []
                time_per_lat_long = {}
                for i in range(len(top_20_paintings_lat)):
                    lat = top_20_paintings_lat[i]
                    longi = top_20_paintings_long[i]
                    
                    time_spent = time_spent_per_lat_long[(time_spent_per_lat_long['lat']==lat) & (time_spent_per_lat_long['lon']==longi)]

                    if time_spent.empty:
                        time_per_lat_long[(lat,longi)] = 0
                    else:    
                        time_per_lat_long[(lat,longi)] = time_spent['time_spent'].sum()



                sorted_time_spent = sorted(time_per_lat_long.items(), key=lambda t: t[1], reverse=True)
                # Code for recommendation ends here



                json_data = []
                for row in sorted_time_spent:
                    json_data.append({"time": row[1], "center": {'lat': row[0][0], 'lng': row[0][1]}})


                return render_template('dashboard.html', name=current_user.name, user_type=current_user.user_type, painting_added=json_data, login='')
        
            else:
                painting_features = {
                    "artist": request.form['artist'],
                    "type_art": request.form['type_art'],
                }
                mongodb.paintings.insert(painting_features)


                # Code for recommendation starts here
                art_data_file = pd.read_csv('static/art_features.csv')

                art_features = art_data_file.drop(['Category','Year','Link','Title', 'Latitude','Longitude','Country'], axis=1)

                painting_to_be_installed = pd.DataFrame([[request.form['artist'], request.form['type_art']]], columns=['Creator ', 'Type'])

                painting_to_be_installed = painting_to_be_installed.iloc[0]



                from sklearn import preprocessing

                # category = preprocessing.LabelEncoder()
                # category.fit(art_features['Category'])
                # art_features['Category'] = category.transform(art_features['Category'])

                creator = preprocessing.LabelEncoder()
                creator.fit(art_features['Creator '])
                art_features['Creator '] = creator.transform(art_features['Creator '])

                art_type = preprocessing.LabelEncoder()
                art_type.fit(art_features['Type'])
                art_features['Type'] = art_type.transform(art_features['Type'])


                new_painting = []
                #new_painting.append(category.transform([painting_to_be_installed['Category']])[0])
                new_painting.append(creator.transform([painting_to_be_installed['Creator ']])[0])
                #new_painting.append(painting_to_be_installed['Year'])
                new_painting.append(art_type.transform([painting_to_be_installed['Type']])[0])


                from sklearn.metrics import jaccard_similarity_score
                sim_scores = []
                min_sim_score = 0
                for index, painting in art_features.iterrows():
                    sim_scores.append(jaccard_similarity_score(painting, new_painting))

                top_20_sim_paintings_index = sorted(range(len(sim_scores)), key=lambda k: sim_scores[k], reverse = True)[:20]


                top_20_paintings = art_data_file.iloc[top_20_sim_paintings_index]
                top_20_paintings_lat = top_20_paintings['Latitude']
                top_20_paintings_long = top_20_paintings['Longitude']


                time_spent_per_lat_long = pd.read_csv('static/one_day.csv')


                time_spent = []
                time_per_lat_long = {}




                for i in top_20_paintings_lat.keys():
                    lat = top_20_paintings_lat[i]
                    longi = top_20_paintings_long[i]
                    
                    time_spent = time_spent_per_lat_long[(time_spent_per_lat_long['lat']==lat) & (time_spent_per_lat_long['lon']==longi)]

                    if time_spent.empty:
                        time_per_lat_long[(lat,longi)] = 0
                    else:    
                        time_per_lat_long[(lat,longi)] = time_spent['time_spent'].sum()



                sorted_time_spent = sorted(time_per_lat_long.items(), key=lambda t: t[1], reverse=True)
                # Code for recommendation ends here



                json_data = []
                for row in sorted_time_spent:
                    json_data.append({"time": row[1], "center": {'lat': row[0][0], 'lng': row[0][1]}})



                return render_template('dashboard.html', name=current_user.name, user_type=current_user.user_type, painting_added=json_data, login='false')
           





















        else:
            # xls = pd.ExcelFile("static/tableau_dic.xls")
            # sheetX = xls.parse(0)
            # json_data = []
            # for row in sheetX.values:
            #     json_data.append({"time": row[3], "center": {'lat': row[1], 'lng': row[2]}})



            currentUser = mongodb.users.find_one({'email': current_user.email})



            if current_user.user_type == 'Customer' and currentUser['login'] == 'true':


                data_file = pd.read_csv('static/one_day.csv')


                mac_lat_lon_grouped= data_file.groupby(['mac'])



                dic_mac={}
                dic_lat={}
                for name, group in mac_lat_lon_grouped:
                    
                    mac=name
                    lat_long=(float(group['lat']),float(group['lon']))
                    #print(lat_long)
                    dic_mac[mac]={}
                    dic_lat[lat_long]={}
                    dic_mac[mac][lat_long]=float(group['time_spent'])
                    dic_lat[lat_long][mac]=float(group['time_spent'])





                test_list = []
                for loca in currentUser['location']:
                    test_list.append((loca['lat'], loca['long']))

            



                usersss=[281903,281841,
                        281826,281819,
                        281796,281780,
                        281771,281763,
                        281747,281744,281726,
                        281708,281661,
                        281649,281641,
                        281637,281609,
                        281597,281592,281582,281576,281567,281564,
                        281563,281545,281544,281540,281538,281537,281524,281523,281503,281496,
                        281491,281481,
                        281479,281469,281463,281458,
                        281457,281455,
                        281453,281445,281437,281430,
                        281424]




                result = []
                for i in range(len(usersss)):
                    user_id,business_id = usersss[i], test_list[i]

                    train_user_bus = dic_mac
                    train_bus_user = dic_lat


                    if train_user_bus.get(user_id):#check whether the user is present in th training data
                        index_user_id=0#pointer to the list of user1 businesses
                        sum_user_1=0#sum for the user1
                        sum_user_2=0#sum for user2
                        list_of_bus1_index=[]#stores the pointer to the list_of_item1
                        list_of_bus2_index=[]#stores the pointer to the list_of_item2
                        corated_ratings=-1#this is the value contained of the user2 for the item to be predicted
                        active_user_bus=list(train_user_bus.get(user_id))#list of businessses for user_1 active user

                        bus_rat_act=train_user_bus.get(user_id)#fetch all the {business:rating} of the user

                        rat_total_act=sum(bus_rat_act.values())
                        length_act=len(active_user_bus)#number of items in the userA
                        weight_list=[]
                        
                        if (train_bus_user.get(business_id)==None):
                            avg_act=rat_total_act/len(list(bus_rat_act))
                            result.append((business_id,str(avg_act)))
                        else:
                            corated_users=list(train_bus_user.get(business_id))#
                            if(len(corated_users)!=0):
                                avg_act=rat_total_act/len(list(bus_rat_act))# average of the userA
                                for i in range(len(corated_users)):
                                    del list_of_bus1_index[:]# clearing
                                    del list_of_bus2_index[:]# clea
                                    sum_user_1=0#sum 
                                    sum_user_2=0#sum 
                                    index_user_id=0

                                    ### value of ratings for that business id by corated users
                                    corated_ratings=train_user_bus[corated_users[i]].get(business_id)#value of the rating for the business rating for the business to be found

                                    #print("This is value of required",value_of_required)
                                    ################### adding my logic of pearson from here 

                                    #user_id_2=str(corated_users[i])

                                    #weight=0.0
                                    #sum2_avg=0.0
                                    #weight,sum2_avg = calculatePearsonSimilarity(train_user_bus,user_id,user_id_2)

                                    while(index_user_id<length_act):#loop until the number of businesses in the userA
                                        if(train_user_bus[corated_users[i]].get(active_user_bus[index_user_id])):
                                            sum_user_1+=train_user_bus[user_id].get(active_user_bus[index_user_id])
                                            sum_user_2+=train_user_bus[corated_users[i]].get(active_user_bus[index_user_id])
                                            list_of_bus2_index.append(train_user_bus[corated_users[i]].get(active_user_bus[index_user_id]))
                                            list_of_bus1_index.append(train_user_bus[user_id].get(active_user_bus[index_user_id]))
                                        index_user_id+=1
                                    index_user_id=0
                                    if len(list_of_bus1_index)!=0:
                                        averageUser1=sum_user_1/len(list_of_bus1_index)
                                        averageUser2=sum_user_2/len(list_of_bus2_index)
                                        numerator=0
                                        denominator=0
                                        denA=0
                                        denB=0
                                        weight=0
                                        val1=0
                                        val2=0
                                        for i in range(len(list_of_bus1_index)):
                                            val1=list_of_bus1_index[i]-averageUser1
                                            val2=list_of_bus2_index[i]-averageUser2
                                            numerator+=(val1*val2)
                                            denA+=val1*val1
                                            denB+=val2*val2
                                        denominator=math.sqrt(denA)*math.sqrt(denB)
                                        if denominator !=0:
                                            weight=numerator/denominator

                                    ############################ till here ###################################
                           #                                 
                                        ratesdifference=0
                                        ratesdifference=(corated_ratings -averageUser2 )* weight
                                        weight_list.append((ratesdifference,weight))
                                #print(list(listOfWeightRate))
                                final_num = sum(n for n,_ in weight_list)
                                final_den = sum(abs(n) for _,n in weight_list)
                                predicted_rating=-1
                                if final_num==0 or final_den==0:
                                    predicted_rating=avg_act
                                    result.append((business_id,str(predicted_rating)))
                                else:
                                    predicted_rating = (final_num / final_den)
                                    predicted_rating += avg_act
                                    if(predicted_rating>5.0):
                                        predicted_rating=5.0
                                    elif(predicted_rating<0.0):
                                        predicted_rating=0.0
                                    result.append((business_id,str(predicted_rating)))
                            else:
                                result.append((business_id,str("3.0")))  ### putting the average
                    else:
                        result.append((business_id,str("3.0")))




                json_data = []
                for row in result:
                    json_data.append({"time": row[1], "center": {'lat': row[0][0], 'lng': row[0][1]}})





                return render_template('dashboard.html', name=current_user.name, user_type=current_user.user_type, painting_added=json_data, login='true')




























            if 'login' in currentUser and currentUser['login'] == 'true':
                return render_template('dashboard.html', json_data=json_data, name=current_user.name, user_type=current_user.user_type, painting_added='', login='true')
            else:
                mongodb.users.update({"email": currentUser['email']}, {'$set': {'login': 'true'}})
                return render_template('dashboard.html', json_data=json_data, name=current_user.name, user_type=current_user.user_type, painting_added='', login='false')

    @app.route('/logout', methods = ['GET'])
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('home'))

    return app

if __name__=='__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
