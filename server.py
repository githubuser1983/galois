import falcon,hashlib
import json,sqlite3
from titus.genpy import PFAEngine
import os.path


class GaloisServer(object):
    def __init__(self,queries,cache):
        self.queries = queries
        self.cache = cache


    def is_path_model(self,path):
        return path.endswith(".pfa")

    def is_path_dir(self,path):
        return not self.is_path_model(path)

    def path_exists(self,path):
        if self.queries.can_rwx("root",path) is None:
            return False
        else:
            return True
        
    def on_get_dir(self,request,response):
        url = request.path
        try:
            # list directory
            ls = ""
            for lsobj in self.queries.list_dir(url):
                filename,user_name,group_name,read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other = lsobj
                ls += "%s,o=%s,g=%s:ro=%s,wo=%s,xo=%s,rg=%s;wg=%s,xg=%s,rot=%s;wot=%s,xot=%s\n" % (filename,user_name,group_name,read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other)
            response.body = ls
            response.status = falcon.HTTP_200
        except Exception, e:
            response.body = "%s not found,%s" % (url,e)
            response.status = falcon.HTTP_404

    def on_get_model(self,request,response):
        url = request.path
        
        path,file_id,parent_id,content,engine = self.cache.getFile(url)
        if not content is None:
            # print content of file
            response.body = content
            response.status = falcon.HTTP_200
        else:
            response.body = "%s not found" % url
            response.status = falcon.HTTP_404

    def on_post_dir(self,request,response):
        url = request.path
        try:
            name = request.get_header("filename")
            username = request.get_header("username")
            if not name.endswith(".pfa"):
                raise Exception("not supported file: %s" % name)
            path,file_id,parent_id,content,engine = self.cache.getFile(url)
            # post model to directory if it does not exist
            if not self.path_exists(os.path.join(url,name)):
                content = request.stream.read(request.content_length or 0)
                engine, = PFAEngine.fromJson(json.loads(content))
                engine.begin()
                # read the file-rights of the directory
                read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other = self.cache.getFileRights(file_id)
                owner_id, group_id = self.cache.getFileOwners(file_id)
                new_file_id = self.queries.insertFile(
                   content = content,
                   name = name,
                   parent_id = file_id,
                   owner_id = owner_id,
                   group_id = group_id,
                   read_owner = read_owner,
                   write_owner = write_owner,
                   execute_owner = execute_owner,
                   read_group = read_group,
                   write_group = write_group,
                   execute_group = execute_group,
                   read_other = read_other,
                   write_other = write_other,
                   execute_other = execute_other
                )
                # insert new file in cache
                newfilepath = os.path.join(url,name)
                self.cache.path2file[newfilepath] = (newfilepath,new_file_id,parent_id,content,engine)
                self.cache.filesMetaData[new_file_id] = (owner_id, group_id, read_owner,read_group,read_other,write_owner,write_group,write_other,execute_owner,execute_group,execute_other)
                response.status = falcon.HTTP_200
            else:
                modelpath = os.path.join(url,name)
                response.body = "%s already exists. try PUT %s" % (modelpath,modelpath)
                response.status = falcon.HTTP_409 # Conflict, model already exists
        except Exception, e:
            response.body = "%s an error occured, %s" % (url,e)
            response.status = falcon.HTTP_505
    
    def on_post_model(self,request,response):
        url = request.path
        try:
            path,file_id,parent_id,content,engine = self.cache.getFile(url)
            # execute model
            d = json.loads(request.stream.read(request.content_length or 0))
            resp = engine.action(d)
            response.media = resp
            response.status = falcon.HTTP_200
        except Exception, e:
            response.body = "%s not found, %s" % (url,e)
            response.status = falcon.HTTP_404

    def on_put_dir(self,request,response):
        url = request.path
        
        try:
            name = request.get_header("filename")
            path,file_id,parent_id,content,engine = self.cache.getFile(url)
            # create new subdirectory if it does not exist, otherwise do not do anything
            if not self.path_exists(os.path.join(url,name)):
                # read the file-rights of the directory
                read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other = self.cache.getFileRights(file_id)
                owner_id, group_id = self.cache.getFileOwners(file_id)
                new_file_id = self.queries.insertFile(
                   content = None,
                   name = name,
                   parent_id = file_id,
                   owner_id = owner_id,
                   group_id = group_id,
                   read_owner = read_owner,
                   write_owner = write_owner,
                   execute_owner = execute_owner,
                   read_group = read_group,
                   write_group = write_group,
                   execute_group = execute_group,
                   read_other = read_other,
                   write_other = write_other,
                   execute_other = execute_other
                )
                # insert new file in cache
                newfilepath = os.path.join(url,name)
                self.cache.path2file[newfilepath] = (newfilepath,new_file_id,parent_id,None,None)
                self.cache.filesMetaData[new_file_id] = (owner_id, group_id, read_owner,read_group,read_other,write_owner,write_group,write_other,execute_owner,execute_group,execute_other)
                response.status = falcon.HTTP_200
            else:
                response.body = "directory %s already exists." % os.path.join(url,name)
                response.status = falcon.HTTP_409
        except Exception, e:
            response.body = "%s not found, %s" % (url,e)
            response.status = falcon.HTTP_404


    def on_put_model(self,request,response):
        url = request.path
        splitted = url.split("/")
        parentpath = os.path.join('/',*splitted[0:-1])
        modelname = splitted[-1]
        if self.path_exists(url):
            path,file_id,parent_id,content,engine = self.cache.getFile(url)
            # overwrite content, restart engine
            newcontent = request.stream.read(request.content_length or 0)
            newengine, = PFAEngine.fromJson(json.loads(newcontent))
            newengine.begin()
            self.queries.updateFile(file_id = file_id,content = newcontent)
            # update cache
            self.cache.path2file[url] = (url,file_id,parent_id,newcontent,newengine)
        elif self.path_exists(parentpath) and self.is_path_dir(parentpath): # create model in dir, if parent directory exists, start engine
            path,file_id,parent_id,content,engine = self.cache.getFile(parentpath)
            content = request.stream.read(request.content_length or 0)
            engine, = PFAEngine.fromJson(json.loads(content))
            engine.begin()
            # read the file-rights of the directory
            read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other = self.cache.getFileRights(file_id)
            owner_id, group_id = self.cache.getFileOwners(file_id)
            new_file_id = self.queries.insertFile(
               content = content,
               name = modelname,
               parent_id = file_id,
               owner_id = owner_id,
               group_id = group_id,
               read_owner = read_owner,
               write_owner = write_owner,
               execute_owner = execute_owner,
               read_group = read_group,
               write_group = write_group,
               execute_group = execute_group,
               read_other = read_other,
               write_other = write_other,
               execute_other = execute_other
            )
            # insert new file in cache
            self.cache.path2file[url] = (url,new_file_id,parent_id,content,engine)
            self.cache.filesMetaData[new_file_id] = (owner_id, group_id, read_owner,read_group,read_other,write_owner,write_group,write_other,execute_owner,execute_group,execute_other)            
            response.status = falcon.HTTP_200
        else:
            response.body = "%s not found" % url
            response.status = falcon.HTTP_404


    def on_delete_dir(self,request,response):
        url = request.path
        try:
            path,file_id,parent_id,content,engine = self.cache.getFile(parentpath)
            if self.queries.is_empty_dir(url):
                self.queries.deleteFile(file_id)
                del self.cache.path2file[file_id]
        except Exception,e: # dir does not exist,  -> return 404
            response.status = falcon.HTTP_404
            return 
        response.status = falcon.HTTP_200       
 
    def on_delete_model(self,request,response):
        url = request.path
        try:
            path,file_id,parent_id,content,engine = self.cache.getFile(url)
            self.queries.deleteFile(file_id)
            del self.cache.path2file[file_id]
            del self.cache.fileMetaData[file_id]
        except Exception,e: # file does not exist,  -> return 404
            response.status = falcon.HTTP_404
            return 
        response.status = falcon.HTTP_200       

    def on_delete(self, request,response):
        username = request.get_header("username")
        url = request.path
        if self.path_exists(url):
            r,w,x = self.queries.can_rwx(username,url)
            if self.is_path_model(url) and w:
                self.on_delete_model(request,response)
            elif self.is_path_dir(url) and w:
                self.on_delete_dir(request,response)
            else:
                response.body = "505 : (%s,%s)" % (username,url)
                response.status = falcon.HTTP_505
        else:
            response.body = "404 : %s" % url
            response.status = falcon.HTTP_404


    def on_get(self, request,response):
        username = request.get_header("username")
        url = request.path
        if self.path_exists(url):
            r,w,x = self.queries.can_rwx(username,url)
            if self.is_path_model(url) and r:
                self.on_get_model(request,response)
            elif self.is_path_dir(url) and r:
                self.on_get_dir(request,response)
            else:
                response.body = "505 : (%s,%s)" % (username,url)
                response.status = falcon.HTTP_505
        else:
            response.body = "404 : %s" % url
            response.status = falcon.HTTP_404


    def on_post(self, request,response):
        username = request.get_header("username")
        url = request.path
        if self.path_exists(url):
            r,w,x = self.queries.can_rwx(username,url)
            if self.is_path_model(url) and x:
                self.on_post_model(request,response)
            elif self.is_path_dir(url) and w:
                self.on_post_dir(request,response)
            else:
                response.body = "505 : (%s,%s)" % (username,url)
                response.status = falcon.HTTP_505
        else:
            response.body = "404 : %s" % url
            response.status = falcon.HTTP_404

    def on_put(self, request,response):
        username = request.get_header("username")
        url = request.path
        splitted = url.split("/")
        parentpath = os.path.join('/',*splitted[0:-1])
        modelname = splitted[-1]
        if self.path_exists(parentpath):
            r,w,x = self.queries.can_rwx(username,parentpath)
            if self.is_path_model(url) and w:
                self.on_put_model(request,response)
            elif self.is_path_dir(url) and w:
                self.on_put_dir(request,response)
            else:
                response.body = "505 : (%s,%s)" % (username,url)
                response.status = falcon.HTTP_505
        else:
            response.body = "404 : %s" % url
            response.status = falcon.HTTP_404

    def on_patch(self,request,response):
        username = request.get_header("username")
        if username=="root" or self.queries.user_is_owner(username,request.path):
            try:
                owner_name = request.get_header("owner_name")
                group_name = request.get_header("group_name")
                read_owner = bool(int(request.get_header("read_owner")))                
                write_owner = bool(int(request.get_header("write_owner")))                
                execute_owner = bool(int(request.get_header("execute_owner")))                
                read_group = bool(int(request.get_header("read_group")))                
                write_group = bool(int(request.get_header("write_group")))                
                execute_group = bool(int(request.get_header("execute_group")))                
                read_other = bool(int(request.get_header("read_other")))                
                write_other = bool(int(request.get_header("write_other")))                
                execute_other = bool(int(request.get_header("execute_other")))                
                owner_id = self.queries.get_uid(owner_name)
                group_id = self.queries.get_gid(group_name)
                path,file_id,parent_id,content,engine = self.cache.getFile(request.path)
                self.queries.updateFileMetaData(file_id,owner_id,group_id,read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other)
                self.cache.filesMetaData[file_id] = (owner_id, group_id, read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other)
                response.body = "200"
                response.status = falcon.HTTP_200
            except Exception,e :
                response.body = "403 : %s " % e
                response.status = falcon.HTTP_403
                return 
        else:
            response.body = "403: (%s,%s)" % (request.path, username)
            response.status = falcon.HTTP_403


def router(request,response):
    username = request.get_header("username")
    pw = request.get_header("password")
    try:
        m = hashlib.sha256()
        m.update(pw)
        hpw = m.digest()
        if galoisServer.queries.user_has_pw(username,hpw):
            if request.method == 'DELETE':
                galoisServer.on_delete(request,response)
            if request.method == 'GET':
                galoisServer.on_get(request,response)
            if request.method == 'PUT':
                galoisServer.on_put(request,response)
            if request.method == 'POST':
                galoisServer.on_post(request,response)
            if request.method == 'PATCH':
                galoisServer.on_patch(request,response)
        else:
            response.body = "505"
            response.status = falcon.HTTP_505
    except Exception,e:
            response.body = "505 : %s" % e
            response.status = falcon.HTTP_505




class Conn(object):
    def __init__(self, sqlitefile = "galois.db"):
        self.db = sqlite3.connect(sqlitefile)
        self.db.text_factory = str


class Queries(object):
    def __init__(self,db):
        self.db = db
        self.cursor = self.db.cursor()

    def get_uid(self,user_name):
        sql = """select uid from s_user where name = ?;"""
        return self.cursor.execute(sql, (user_name,)).fetchone()[0]

    def get_gid(self,group_name):
        sql = """select gid from s_group where name = ?;"""
        return self.cursor.execute(sql, (group_name,)).fetchone()[0]
            
    def updateFileMetaData(self,file_id,owner_id,group_id,read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other):
        sql = """update s_file set owner_id = ?,group_id=?, read_owner=?, write_owner=?, execute_owner=?, read_group=?, write_group=?, execute_group=?, read_other=?, write_other=?, execute_other=? where file_id = ?;"""
        self.cursor.execute(sql, (owner_id,group_id,read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other,file_id,))
        self.db.commit()


    def deleteFile(self, file_id):
        sql = """delete from s_file where file_id = ?;"""
        self.cursor.execute(sql,(file_id,))
        self.db.commit()

    def updateFile(self, file_id,content):
        sql = """update s_file set content = ? where file_id = ?"""
        self.cursor.execute(sql, (sqlite3.Binary(content),file_id,))
        self.db.commit()
        
    def insertFile(self,content,name,parent_id,owner_id,group_id,read_owner,write_owner,
                   execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other):
         sql = """insert into s_file(content,name,parent_id,owner_id,group_id,read_owner,write_owner,execute_owner, 
                                     read_group,write_group,execute_group,read_other,write_other,execute_other) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?);"""
         self.cursor.execute(sql,(content,name,parent_id,owner_id,group_id,read_owner,write_owner,
                   execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other,))
         self.db.commit()
         return self.cursor.lastrowid

    def user_has_pw(self,username,hpw):
         sql = """select name from s_user where name = ? and password = ? """
         row = self.cursor.execute(sql,(username,hpw,)).fetchone()
         return not (row is None)


    def can_rwx(self,user_name,path):
        sql = """select can_write,can_read,can_execute from global_rights gr left join s_user u on gr.uid = u.uid where u.name = ? and gr.path = ?"""
        can = self.cursor.execute(sql,(user_name,path,)).fetchone()
        if can is None:
            return None
        elif user_name == "root":
            return (True,True,True)
        else:
            w,r,x = can
            return (r,w,x)

    def list_dir(self,path):
        sql = """select  lr.name as file_name, u.name as user_name, g.name as group_name, f.read_owner, f.write_owner, f.execute_owner, f.read_group, f.write_group, f.execute_group, f.read_other, f.write_other, f.execute_other from local_rights lr left join global_rights gr on lr.uid = gr.uid and lr.parent_id = gr.file_id left join s_file f on f.file_id = lr.file_id left join s_user u on u.uid = f.owner_id left join s_group g on g.gid = f.group_id where gr.path = ? and lr.uid = 1;"""
        ls = self.cursor.execute(sql,(path,)).fetchall()
        if len(ls)==0 or ls is None:
            return []
        else:
            return [ls[i] for i in range(len(ls))]

    def is_empty_dir(self,path):
        return len(self.list_dir(path)) == 0

    def user_is_owner(self,username, path):
        sql = """select case when f.owner_id = u.uid then 1 else 0 end as user_is_owner from global_rights gr left join s_user u on gr.uid = u.uid left join s_file f on f.file_id = gr.file_id where u.name = ? and gr.path = ?"""
        user_is_owner = self.cursor.execute(sql,(username,path,)).fetchone()[0]
        return user_is_owner

class Cache(object):
    def __init__(self,db):
        self.db = db
        self.cursor = self.db.cursor()
        self.__load_cache()

    def __load_cache(self):
        fileMetaData = self.cursor.execute("select file_id, owner_id, group_id, read_owner,write_owner,execute_owner,read_group,write_group,execute_group,read_other,write_other,execute_other from s_file;").fetchall()
        self.filesMetaData = dict([ (fileMetaData[i][0],fileMetaData[i][1:]) for i in range(len(fileMetaData))] )
        files = self.cursor.execute("select gr.path,f.file_id,f.parent_id, f.content from s_file f  left join global_rights gr on f.file_id = gr.file_id where gr.uid = 1").fetchall()
        self.path2file = {}
        for file in files:
            path,file_id,parent_id,content = file
            if not content is None:
                content = str(content)
                engine, = PFAEngine.fromJson(json.loads(content))
                engine.begin()
                self.path2file[path] =  (path,file_id,parent_id,content, engine)
            else:
                self.path2file[path] = (path,file_id,parent_id,None,None)

    def getFile(self,path):
        if path in self.path2file.keys():
            return self.path2file[path]
        else:
            return None

    def getFileOwners(self,file_id):
        if file_id in self.filesMetaData.keys():
            return self.filesMetaData[file_id][0:2]
        else:
            return None


    def getFileRights(self,file_id):
        if file_id in self.filesMetaData.keys():
            return self.filesMetaData[file_id][2:]
        else:
            return None
        
#logging.basicConfig(filename='server.log',level=logging.INFO)
conn = Conn()
qr = Queries(conn.db)
cache = Cache(conn.db)

galoisServer = GaloisServer(queries = qr,cache=cache)


api = falcon.API()

api.add_sink(router,'/galois.*')

#only for root

#/user 
#GET: list of all usernames
#PUT: create or overwrite specific user
#DELETE: delete specific user

#/group
#GET: list of all groups
#PUT: create or overwrite specific group
#DELETE: delete specific group

#/user_in_group
#GET: list all users in which groups
#PUT: create or overwrite (user,group) in the list
#DELETE: delete specific (user,group) from the list

class User(object):
    def __init__(self, queries):
         self.queries = queries

    def list_users(self):
        return self.queries.cursor.execute("select name from s_user;").fetchall()

    def put_user(self,username,password):
        m = hashlib.sha256()
        m.update(password)
        password = m.digest()
        self.queries.cursor.execute("insert or replace into s_user(name,password) values (?,?);",(username,password,))
        self.queries.db.commit()

    def delete_user(self,username):
        # make all files which are owned by user belong to root:
        userid = self.queries.cursor.execute("select uid from s_user where name = ?;", (username,)).fetchone()[0]
        self.queries.cursor.execute("update s_file set owner_id = 1 where owner_id = ?;",(userid,))
        # delete user
        self.queries.cursor.execute("delete from s_user where name = ?;",(username,))
        self.queries.db.commit()

    def on_get(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")       
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw):
                users = self.list_users()
                ls = ""
                for user in users:
                    ls += user[0] + "\n"
                response.body = ls
                response.status = falcon.HTTP_200
            else:
                response.body = "username and password do not match"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, no username or password given" % e
            response.status = falcon.HTTP_403

    def on_put(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")
            newuser = request.get_header("newusername")
            newpassword = request.get_header("newpassword")       
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            M = hashlib.sha256()
            M.update(newpassword)
            nhpw = M.digest()
            if self.queries.user_has_pw(username,hpw) and username=="root":
                self.put_user(newuser, nhpw)
                response.status = "user %s created or updated" % newuser
                response.status = falcon.HTTP_200
            else:
                response.body = "you are not root. only root can put users"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, you have to supply the following http-headers: username, password, newusername, newpassword" % e
            response.status = falcon.HTTP_403

    def on_delete(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")       
            deluser = request.get_header("delusername")
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw) and username == "root":
                self.delete_user(deluser)
                response.body = "user %s deleted. all his files belong to root now." % deluser
                response.status = falcon.HTTP_200
            else:
                response.body = "username and password do not match"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, please provide the following http-headers: username, password, delusername = which user should be deleted?" % e
            response.status = falcon.HTTP_403


user = User(qr)
api.add_route('/user', user)

class Group(object):
    def __init__(self, queries):
         self.queries = queries

    def list_groups(self):
        return self.queries.cursor.execute("select name from s_group;").fetchall()

    def put_group(self,groupname):
        self.queries.cursor.execute("insert or replace into s_group(name) values (?);",(groupname,))
        self.queries.db.commit()

    def delete_group(self,groupname):
        # make all files which are owned by group belong to root-group:
        gid = self.queries.cursor.execute("select gid from s_group where name = ?;", (groupname,)).fetchone()[0]
        self.queries.cursor.execute("update s_file set group_id = 1 where group_id = ?;",(gid,))
        # delete group
        self.queries.cursor.execute("delete from s_group where name = ?;",(groupname,))
        self.queries.db.commit()

    def on_get(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")       
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw):
                groups = self.list_groups()
                ls = ""
                for group in groups:
                    ls += group[0] + "\n"
                response.body = ls
                response.status = falcon.HTTP_200
            else:
                response.body = "username and password do not match"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, no username or password given" % e
            response.status = falcon.HTTP_403

    def on_put(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")
            groupname = request.get_header("groupname")
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw) and username=="root":
                self.put_group(groupname)
                response.status = "group %s created or updated" % groupname
                response.status = falcon.HTTP_200
            else:
                response.body = "you are not root. only root can put groups"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, you have to supply the following http-headers: username, password, groupname" % e
            response.status = falcon.HTTP_403

    def on_delete(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")       
            delgroup = request.get_header("delgroup")
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw) and username == "root":
                self.delete_group(delgroup)
                response.body = "group %s deleted. all his files belong to root now." % delgroup
                response.status = falcon.HTTP_200
            else:
                response.body = "username and password do not match"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, please provide the following http-headers: username, password, delgroup = which group should be deleted?" % e
            response.status = falcon.HTTP_403

group = Group(qr)
api.add_route('/group', group)


class UserInGroup(object):
    def __init__(self, queries):
         self.queries = queries

    def list_uigs(self):
        return self.queries.cursor.execute("select u.name, g.name from s_user_in_group uig left join s_user u on uig.uid = u.uid left join s_group g on g.gid = uig.gid;").fetchall()

    def put_uig(self,username, groupname):
        uid = self.queries.cursor.execute("select uid from s_user where name = ?", (username,)).fetchone()[0]
        gid = self.queries.cursor.execute("select gid from s_group where name = ?", (groupname,)).fetchone()[0]
        self.queries.cursor.execute("insert or replace into s_user_in_group(uid,gid) values (?,?);",(uid,gid,))
        self.queries.db.commit()

    def delete_uig(self,username,groupname):
        uid = self.queries.cursor.execute("select uid from s_user where name = ?", (username,)).fetchone()[0]
        gid = self.queries.cursor.execute("select gid from s_group where name = ?", (groupname,)).fetchone()[0]
        # delete user in group
        self.queries.cursor.execute("delete from s_user_in_group where uid = ? and gid = ?;",(uid,gid,))
        self.queries.db.commit()

    def on_get(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")       
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw):
                uigs = self.list_uigs()
                ls = ""
                for uig in uigs:
                    ls += uig[0]+","+uig[1] + "\n"
                response.body = ls
                response.status = falcon.HTTP_200
            else:
                response.body = "username and password do not match"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, no username or password given" % e
            response.status = falcon.HTTP_403

    def on_put(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")
            putgroup = request.get_header("putgroup")
            putuser = request.get_header("putuser")
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw) and username=="root":
                self.put_uig(putuser,putgroup)
                response.status = "uig (%s,%s) created or updated" % (putuser,putgroup)
                response.status = falcon.HTTP_200
            else:
                response.body = "you are not root. only root can put users in groups"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, you have to supply the following http-headers: username, password, putuser,putgroup" % e
            response.status = falcon.HTTP_403

    def on_delete(self,request,response):
        try:
            username = request.get_header("username")
            pw = request.get_header("password")       
            delgroup = request.get_header("delgroup")
            deluser = request.get_header("deluser")
            m = hashlib.sha256()
            m.update(pw)
            hpw = m.digest()
            if self.queries.user_has_pw(username,hpw) and username == "root":
                self.delete_uig(deluser,delgroup)
                response.body = "user in group (%s, %s) deleted" % (deluser,delgroup)
                response.status = falcon.HTTP_200
            else:
                response.body = "username and password do not match"
                response.status = falcon.HTTP_403
        except Exception,e:
            response.body = "403 : %s, please provide the following http-headers: username, password, deluser, delgroup = which group should be deleted?" % e
            response.status = falcon.HTTP_403

uig = UserInGroup(qr)
api.add_route('/uig',uig)


