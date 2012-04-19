from django.http import HttpResponse, HttpResponseServerError
from gitstack.models import Repository, UserApache, Apache, Group
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.conf import settings

import json, re, os, jsonpickle, logging, ConfigParser, ldap #@UnresolvedImport 
logger = logging.getLogger('console')

# user rest api
@csrf_exempt
def rest_user(request):
    try:
        # create user
        if request.method == 'POST':
            # get the username/password from the request
            username = request.POST['username']
            password = request.POST['password']
            user = UserApache(username, password)
            user.create()
            return HttpResponse("User created")
        # get retrieve_all the users
        if request.method == 'GET':
            # convert list of objects to list of strings
            user_list_str = []
            user_list_obj = UserApache.retrieve_all()
            for user in user_list_obj:   
                user_list_str.append(user.username)
            json_reply = json.dumps(user_list_str)
            return HttpResponse(json_reply)
        # update the user
        if request.method == 'PUT':
            # retrieve the credentials from the json
            credentials = json.loads(request.raw_post_data)
            # create an instance of the user and update it
            user = UserApache(credentials['username'], credentials['password'])
            user.update()
            return HttpResponse("User successfully updated")
        
    except Exception as e:
        return HttpResponseServerError(e)
    
# group rest api
@csrf_exempt
def rest_group(request):
    try:
        # create a group
        if request.method == 'POST':
            # get the username/password from the request
            name = request.POST['name']
            group = Group(name)
            group.create()
            return HttpResponse("Group " + name + " has been successfully created." )
        
        # get retrieve_all the groups
        if request.method == 'GET':
            group_list = Group.retrieve_all()
            json_reply = jsonpickle.encode(group_list, unpicklable = False)

            return HttpResponse(json_reply)
        
    except Exception as e:
        return HttpResponseServerError(e)

# web interface (gitweb) rest api
@csrf_exempt
def webinterface(request):
    try:
        # get if the web interface is enabled
        
        gitphp_path = settings.INSTALL_DIR + '/apache/conf/gitstack/gitphp.conf'
        if request.method == 'GET':
            # check if the file gitphp.conf exist
            isEnabled = False
            if os.path.isfile(gitphp_path):
                isEnabled = True
            
            permissions = {'enabled' : isEnabled}
    
            json_reply = json.dumps(permissions)
            return HttpResponse(json_reply)
        
        # update the web interface permissions
        if request.method == 'PUT':
            # retrieve the dictionary from the request
            web_interface_dic = json.loads(request.raw_post_data)
            # update the repository
            isEnabled = web_interface_dic['enabled']
            # rename the file to enable or disable the web interface
            if isEnabled:
                os.rename(gitphp_path + '.disabled', gitphp_path)
            else:
                os.rename(gitphp_path, gitphp_path + '.disabled')

            # restart apache 
            Apache.restart()
            
            # create the message
            if isEnabled:
                message = "Web interface successfully enabled"
            else:
                message = "Web interface successfully disabled"
            return HttpResponse(message)
        
    except Exception as e:
        return HttpResponseServerError(e)

@csrf_exempt
def rest_user_action(request, username):
    try:
        if request.method == 'DELETE':
            # retrieve the username from the json
            user = UserApache(username)
            # delete the user
            user.delete()
            return HttpResponse(username + " has been deleted")
    except Exception as e:
        return HttpResponseServerError(e)
 
@csrf_exempt   
def rest_group_action(request, name):
    try:
        if request.method == 'DELETE':
            # retrieve the group name from the url
            group = Group(name)
            # delete the user
            group.delete()
            return HttpResponse(name + " has been deleted")
    except Exception as e:
        return HttpResponseServerError(e)
    
# Add/Remove users on a repository
@csrf_exempt
def rest_group_user(request, group_name, username):
    group = Group(group_name)
    group.load()
    user = UserApache(username)
    
    # Add member to the group
    if request.method == 'POST':
        group.add_user(user)
        group.save()
        return HttpResponse("User " + username + " added to " + group_name)

    # Remove a group member
    if request.method == 'DELETE':
        group.remove_user(user)
        group.save()
        return HttpResponse(username + " removed from " + group_name)
    
# Get all the users on a specific group
@csrf_exempt
def rest_group_user_all(request, group_name):
    # Get the repository and add the user
    group = Group(group_name)
    group.load()
    users = group.member_list
    logger.debug(len(users))
    users_name = map(lambda foo: foo.__unicode__(), users)
    
    json_reply = json.dumps(users_name)
    return HttpResponse(json_reply)


# create a repository
def rest_repository(request):
    # Add new repository
    if request.method == 'POST':
        name=request.POST['name']
        try:
            # check the repo name
            matcher = re.compile("^[A-Za-z]\w{2,}$")
            if matcher.match(name) is None:
                raise Exception("Please enter an alphanumeric name without spaces")
            if(name == ""):
                raise Exception("Please enter a non empty name")
            # create the repo
            repository = Repository(name)
            repository.create()
        except WindowsError as e:
            return HttpResponseServerError(e.strerror)
        except Exception as e:
            return HttpResponseServerError(e)
        
        return HttpResponse("The repository has been successfully created")
    # List retrieve_all repositories
    if request.method == 'GET':
        try:
            # change to the repository directory
            repositories = Repository.retrieve_all()
            # remove the .git at the end
            
            json_reply = jsonpickle.encode(repositories, unpicklable = False)
            return HttpResponse(json_reply)
        except WindowsError as e:
            return HttpResponseServerError(e.strerror)
        

# delete or update a repository
@csrf_exempt
def rest_repo_action(request, repo_name):
    #try:
    if request.method == 'DELETE':
        repo = Repository(repo_name)
        # delete the repo
        repo.delete()
        return HttpResponse(repo.name + " has been deleted")
    if request.method == 'PUT':
        repo = Repository(repo_name)
        # retrieve data sent by the client
        raw_data = json.loads(request.raw_post_data)
        # retrieve the bare property
        bare = raw_data['bare']
        # if the repository needs to be imported
        
        if repo.bare == False and bare == True:
            # convert the repository
            repo.convert_to_bare()
            
            return HttpResponse("The repository was successfully imported.")
    
        return HttpResponseServerError("The repository was not imported successfully.")
    #except Exception as e:
    #    return HttpResponseServerError(e)
    
    
    

# Add/Remove users on a repository
@csrf_exempt
def rest_repo_user(request, repo_name, username):
    repo = Repository(repo_name)
    user = UserApache(username)

    # Add user
    if request.method == 'POST':
        # Get the repository and add the user
        repo.add_user(user)
        repo.add_user_read(user)
        repo.add_user_write(user)
        repo.save()
        return HttpResponse("User " + username + " added to " + repo_name)
    # Delete the user
    if request.method == 'DELETE':
        # Remove the user from the repository
        repo.remove_user(user)
        repo.save()
        return HttpResponse(username + " removed from " + repo_name)
    # Get the user permissions
    if request.method == 'GET':
        permissions = {'read' : False, 'write' : False}
        # retrieve the list of read and write users
        user_read_list = repo.user_read_list
        user_write_list = repo.user_write_list
        # check if the user has read and write access
        if user in user_read_list:
            permissions['read'] = True
        if user in user_write_list:
            permissions['write'] = True
            
        # reply with the json permission object
        json_reply = json.dumps(permissions)
        return HttpResponse(json_reply)
    
    if request.method == 'PUT':
        # retrieve the credentials from the json
        permissions = json.loads(request.raw_post_data)

        # Get the old password and new password
        if 'read' in permissions:
            # add the read permission to the repo
            if permissions['read']:
                repo.add_user_read(user)
            else:
                repo.remove_user_read(user)

        if 'write' in permissions:
            # add the write permission to the repo
            if permissions['write']:
                repo.add_user_write(user)
            else:
                repo.remove_user_write(user)
                
        repo.save()
        return HttpResponse(user.username + "'s permissions updated")
    

# Add/Remove group on a repository
@csrf_exempt
def rest_repo_group(request, repo_name, group_name):
    repo = Repository(repo_name)
    group = Group(group_name)

    # Add group
    if request.method == 'POST':
        # Get the repository and add the user
        repo.add_group(group)
        repo.add_group_read(group)
        repo.add_group_write(group)
        repo.save()
        return HttpResponse("User " + group_name + " added to " + repo_name)
    
    # Delete the group
    if request.method == 'DELETE':
        # Remove the group from the repository
        repo.remove_group(group)
        repo.save()
        return HttpResponse(group_name + " removed from " + repo_name)
    
    # Get the group permissions
    if request.method == 'GET':
        permissions = {'read' : False, 'write' : False}
        # retrieve the list of read and write users
        group_read_list = repo.group_read_list
        group_write_list = repo.group_write_list
        # check if the user has read and write access
        if group in group_read_list:
            permissions['read'] = True
        if group in group_write_list:
            permissions['write'] = True
            
        # reply with the json permission object
        json_reply = json.dumps(permissions)
        return HttpResponse(json_reply)
    
    if request.method == 'PUT':
        # retrieve the credentials from the json
        permissions = json.loads(request.raw_post_data)

        # Get the old password and new password
        if 'read' in permissions:
            # add the read permission to the repo
            if permissions['read']:
                repo.add_group_read(group)
            else:
                repo.remove_group_read(group)

        if 'write' in permissions:
            # add the write permission to the repo
            if permissions['write']:
                repo.add_group_write(group)
            else:
                repo.remove_group_write(group)
                
        repo.save()
        return HttpResponse(group_name + "'s permissions updated")
    
# Get all the users on a specific repository
@csrf_exempt
def rest_repo_user_all(request, repo_name):
    # Get the repository and add the user
    repo = Repository(repo_name)
    users = repo.user_list
    users_name = map(lambda foo: foo.__unicode__(), users)
    json_reply = json.dumps(users_name)
    return HttpResponse(json_reply)

# Get all the groups on a specific repository
@csrf_exempt
def rest_repo_group_all(request, repo_name):
    # Get the repository and add the user
    repo = Repository(repo_name)
    group_list = repo.group_list
    group__list_names = map(lambda foo: foo.__unicode__(), group_list)
    json_reply = json.dumps(group__list_names)
    return HttpResponse(json_reply)
    
# change admin password
def rest_admin(request):
    # update the user
    if request.method == 'PUT':
        # retrieve the credentials from the json
        passwords = json.loads(request.raw_post_data)
        # Get the old password and new password
        old_password = passwords['oldPassword']
        new_password = passwords['newPassword']
        # Check of the old password is correct 
        user = authenticate(username='admin', password=old_password)
        if user is not None:
            # Change the password
            user.set_password(new_password)
            user.save()
            return HttpResponse("User successfully updated")
        else:
            return HttpResponseServerError("Your current administrator password is not correct.")
        
# Change authentification settings
@csrf_exempt
def rest_settings_authentication(request):
    # Get the settings
    if request.method == 'GET':
        # load the settings file
        config = ConfigParser.ConfigParser()
        config.read(settings.SETTINGS_PATH)
        
        # retrieve the settings
        auth_method = config.get('authentication', 'authmethod')
        ldap_host = config.get('authentication', 'ldaphost')
        ldap_base_dn = config.get('authentication', 'ldapbasedn')
        ldap_bind_dn = config.get('authentication', 'ldapbinddn')
        ldap_bind_password = config.get('authentication', 'ldapbindpassword')
        
        # build json reply
        json_reply = '{"authMethod":"' + auth_method + '","ldap":{"host": "' + ldap_host +'","baseDn": "' + ldap_base_dn +'","bindDn": "' + ldap_bind_dn +'","bindPassword": "' + ldap_bind_password + '"}}'
        # json_reply = '{"authMethod":"ldap","ldap":{"url": "ldap://10.0.1.24:389/","baseDn": "CN=Users,DC=contoso,DC=com","bindDn": "CN=john,CN=Users,DC=contoso,DC=com","bindPassword": "thepassword"}}'
        return HttpResponse(json_reply)
    # Set the settings
    if request.method == 'PUT':
        auth_settings = json.loads(request.raw_post_data)
        
        # load the config file
        config = ConfigParser.ConfigParser()
        config.read(settings.SETTINGS_PATH)
        
        # save the settings
        config.set('authentication', 'authmethod', auth_settings['authMethod'])
        config.set('authentication', 'ldaphost', auth_settings['ldap']['host'])
        config.set('authentication', 'ldapbasedn', auth_settings['ldap']['baseDn'])
        config.set('authentication', 'ldapbinddn', auth_settings['ldap']['bindDn'])
        config.set('authentication', 'ldapbindpassword', auth_settings['ldap']['bindPassword'])
        
      
        f = open(settings.SETTINGS_PATH, "w")
        config.write(f)
        f.close()
        
        
        return HttpResponse("Settings successfully saved.")
    
# authentication ldap
def rest_settings_authentication_ldap_test(request):   
    # retrieve the settings from the request

    ldap_host = request.GET['host']
    ldap_bind_dn = request.GET['bindDn']
    ldap_bind_password = request.GET['bindPassword']
    
    con = ldap.initialize(ldap_host)
    try:
        con.simple_bind_s(ldap_bind_dn,ldap_bind_password)
    except (ldap.INVALID_CREDENTIALS,ldap.LDAPError) as e :
        if type(e.message) == dict and e.message.has_key('desc'):
            return HttpResponseServerError(e.message['desc'])

        else:
            return HttpResponseServerError(e)
    except Exception as e:
        return HttpResponseServerError(e)
        
    finally:
        con.unbind()
        
    return HttpResponse("Ldap server successfully contacted.")




    





