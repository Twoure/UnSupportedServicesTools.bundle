####################################################################################################
#                                                                                                  #
#                           UnSupported Services Tools (Plex Channel)                              #
#                                                                                                  #
####################################################################################################

TITLE = 'UnSupported Services Tools'
PREFIX = '/applications/unsupportedservicestools'

IDENTIFIER = 'com.plexapp.system.unsupportedservices'
INIT_NAME = 'UnSupportedServices'
REPO = 'Twoure/UnSupportedServices.bundle'

ICON = 'icon-default.png'
#ART = 'art-default.jpg'

from ussinstallservice import USSInstallService
USSI = USSInstallService(IDENTIFIER, INIT_NAME)

####################################################################################################
def Start():
    ObjectContainer.title1 = TITLE

    DirectoryObject.thumb = R(ICON)
    #DirectoryObject.art = R(ART)

    HTTP.CacheTime = 0

    Log.Debug('*' * 80)
    Log.Debug('* Platform.OS            = %s' %Platform.OS)
    Log.Debug('* Platform.OSVersion     = %s' %Platform.OSVersion)
    Log.Debug('* Platform.ServerVersion = %s' %Platform.ServerVersion)
    Log.Debug('*' * 80)


####################################################################################################
@handler(PREFIX, TITLE, thumb=ICON)
@route(PREFIX + '/mainmenu')
def MainMenu():

    oc = ObjectContainer(title1=TITLE, no_cache=True)
    USSI.bundleservice.update_bundle_info()
    USSI.setup_current_info(IDENTIFIER)
    pw = True if Client.Product == 'Plex Web' else False

    if bool(USSI.current_info):
        oc.add(DirectoryObject(
            key=Callback(MainMenu),
            title='%s | %s | Installed' %(str(USSI.current_info['date']), USSI.current_info['branch'])
            ))

        if not pw:
            oc.add(PopupDirectoryObject(key=Callback(MainMenu), title='View Tools in Plex Web Client'))
        elif not bool(USSI.update_info):
            oc.add(DirectoryObject(
                key=Callback(ActionMenu, action='init', title='Re-Install \"%s\" branch' %Prefs['branch']),
                title='Re-Install \"%s\" branch' %Prefs['branch'],
                summary='Re-Install \"%s\" branch from latest commit.' %Prefs['branch']
                ))

        if bool(USSI.update_info) and (USSI.update_info['branch'] == Prefs['branch']) and pw:
            oc.add(DirectoryObject(
                key=Callback(ActionMenu, action='update', title='Installing Update'),
                title='%s | %s | Available - Install Update' %(str(USSI.update_info['date']), USSI.update_info['branch']),
                summary=USSI.update_info['notes'] if USSI.update_info['notes'] else None
                ))
        elif bool(USSI.update_info):
            USSI.update_info.clear()

        if pw:
            oc.add(DirectoryObject(
                key=Callback(ActionMenu, action='check_update', title='Checking For Update'),
                title='Check For Update', summary='Check GitHub for latest USS release.'
                ))

        oc.add(DirectoryObject(
            key=Callback(HostMenu),
            title='Supported Host', summary='List Curretnly Supported Host.'
            ))
    elif pw:
        oc.add(DirectoryObject(
            key=Callback(ActionMenu, action='init', title='Initial Install of USS'),
            title='Install New USS',
            summary=(
                'UnSupportedServices (USS) is a collection of Service Code not included within the Official Plex Services.bundle.'
                'UnSupportedServicesTools (USST) will install/update/manage the USS. '
                'This function will install a fresh/current version of the \"%s\" branch USS.' %Prefs['branch']
                )
            ))
    else:
        oc.add(PopupDirectoryObject(key=Callback(MainMenu), title='Install New USS in Plex Web Client ONLY'))

    oc.add(PrefsObject(title='Preferences'))
    oc.add(InputDirectoryObject(
        key=Callback(Search), title='Input Test URL', prompt='Input Test URL'
        ))

    return oc

####################################################################################################
@route(PREFIX + '/action')
def ActionMenu(action, title):
    oc = ObjectContainer(title2=title, no_cache=True)

    branch = Prefs['branch']

    if action == 'check_update':
        header = 'Check for Update'
        message = USSI.gui_update(REPO, branch, check=True)
    elif action == 'update':
        header = 'Update USS'
        message = USSI.gui_update(REPO, branch)
    elif action == 'init':
        header = 'USS Initial Install'
        message = USSI.gui_init_install(REPO, branch)
    else:
        header = 'Action Menu'
        message = 'No Action Taken'

    return MessageContainer(header, message)

####################################################################################################
@route(PREFIX + '/host')
def HostMenu():
    oc = ObjectContainer(title2='Supported Host', no_cache=True)
    host_list = USSI.gui_host_list()
    [oc.add(PopupDirectoryObject(key=Callback(HostMenu), title=h)) for h in host_list if host_list]
    return oc

####################################################################################################
@route(PREFIX + '/test/search')
def Search(query=''):

    url = query.strip()
    url = ('http://' + url if not url.startswith('//') else 'http:' + url) if (not url.startswith('http') and not url.startswith('uss/')) else url
    oc = ObjectContainer(title2='TEST Video URL = %s' %url)
    if URLService.ServiceIdentifierForURL(url):
        try:
            oc.add(URLService.MetadataObjectForURL(url))
        except Exception as e:
            Log.Error(str(e))
            return MessageContainer('Warning', 'This media may have expired.')
    else:
        return MessageContainer('Warning', 'No URL Service for %s' %url)
    return oc
