TITLE = 'UnSupported Services Tools'
PREFIX = '/applications/unsupportedservicestools'
IDENTIFIER = 'com.plexapp.system.unsupportedservices'
UPDATE_URL = 'https://api.github.com/repos/Twoure/UnSupportedServices.bundle/releases/latest'

ICON = 'icon-default.png'
ART = 'art-default.jpg'

from ussinstallservice import USSInstallService
USSI = USSInstallService(IDENTIFIER, UPDATE_URL)

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
    USSI.bundleservice.update_bundle_info(0)
    USSI.info_from_plist(IDENTIFIER)
    pw = True if Client.Product == 'Plex Web' else False

    if bool(USSI.current_info):
        oc.add(DirectoryObject(key=Callback(MainMenu), title='v%s Installed' %USSI.current_info['version']))

        if bool(USSI.update_info) and pw:
            oc.add(DirectoryObject(
                key=Callback(ActionMenu, action='update', title='Installing Update'),
                title='v%s Available - Install Update' %USSI.update_info['version'],
                summary=USSI.update_info['notes'] if USSI.update_info['notes'] else None
                ))

        if not pw:
            oc.add(PopupDirectoryObject(key=Callback(MainMenu), title='Check for Update with Plex Web Client ONLY'))
        else:
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
                'This function will install a fresh/current version of the USS.'
                )
            ))
    else:
        oc.add(PopupDirectoryObject(key=Callback(MainMenu), title='Install New USS in Plex Web Client ONLY'))

    return oc

####################################################################################################
@route(PREFIX + '/action')
def ActionMenu(action, title):
    oc = ObjectContainer(title2=title, no_cache=True)

    if action == 'check_update':
        header = 'Check for Update'
        message = USSI.gui_check_for_update()
    elif action == 'update':
        header = 'Update USS'
        message = USSI.gui_update()
    elif action == 'init':
        header = 'USS Initial Install'
        message = USSI.gui_init_install()
    else:
        header = 'Action Menu'
        message = 'No Action Taken'

    return MessageContainer(header, message)

####################################################################################################
@route(PREFIX + '/host')
def HostMenu():
    oc = ObjectContainer(title2='Supported Host', no_cache=True)
    host_list = USSI.gui_host_list()
    if host_list:
        for h in host_list:
            oc.add(PopupDirectoryObject(key=Callback(HostMenu), title=h))
    return oc
