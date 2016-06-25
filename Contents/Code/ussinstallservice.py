#!/usr/bin/env python
# UnSupportedServices Updater
# Edited by: Twoure
# Date: 06/11/2016

KEY_PLIST_VERSION           = 'CFBundleVersion'
KEY_PLIST_URL               = 'PlexPluginVersionUrl'

KEY_DATA_VERSION            = 'tag_name'
KEY_DATA_DESC               = 'body'
KEY_DATA_ZIPBALL            = 'zipball_url'

#CHECK_INTERVAL              = CACHE_1HOUR * 12
CHECK_INTERVAL              = 0

HISTORY_KEY                 = "_UnSupportedServices:History"

IDENTIFIER_KEY              = "InstallIdentifier"
NOTES_KEY                   = "InstallNotes"
DATE_KEY                    = "InstallDate"
VERSION_KEY                 = "InstallVersion"
ACTION_KEY                  = "InstallAction"

class BundleInfo(object):
    def __init__(self, plugin_path, name):
        self.path = plugin_path
        self.name = name
        self.bundled = Core.bundled_plugins_path in plugin_path if Core.bundled_plugins_path is not None else False
        self.bundle_info = dict()
        self.update_bundle_info()

    def load_plist(self):
        plist = Plist.ObjectFromString(Core.storage.load(Core.storage.join_path(self.path, "Contents", "Info.plist")))
        self.service_dict = Core.services.get_services_from_bundle(self.path, plist)
        self.identifier = plist['CFBundleIdentifier']
        self.ignore = 'PlexPluginDevMode' in plist and plist['PlexPluginDevMode'] == '1'
        self.plugin_class = plist.get('PlexPluginClass', 'Channel')

        if self.plugin_class == 'Agent':
            self.ignore = True

        if Core.storage.link_exists(self.path):
            Log("Plug-in bundle with identifier '%s' is a symbolic link, and will be ignored.", self.identifier)
            self.ignore = True

    def has_services(self):
        for key in ('Services', 'ServiceSets', 'OldServices'):
            for service_type in self.service_dict[self.identifier][key]:
                if len(self.service_dict[self.identifier][key][service_type]) > 0:
                    return True
        return False

    @property
    def info(self):
        return self.bundle_info

    def update_bundle_info(self):
        self.load_plist()
        self.bundle_info = {
            'name': self.name, 'ignore': self.ignore, 'has_services': self.has_services(),
            'bundled': self.bundled, 'identifier': self.identifier
            }

class BundleService(object):
    def __init__(self):
        self.plugins_path = Core.storage.join_path(Core.app_support_path, 'Plug-ins')
        self.bundle_dict = dict()
        self.update_bundle_info()

    @property
    def bundles(self):
        return self.bundle_dict

    def update_bundle_info(self):
        identifiers = []
        plugins_list = XML.ElementFromURL('http://127.0.0.1:32400/:/plugins', cacheTime=0)

        for plugin_el in plugins_list.xpath('//Plugin'):
            identifiers.append(plugin_el.get('identifier'))

        if Core.bundled_plugins_path is not None:
            bundled_plugin_paths = {d : Core.storage.join_path(Core.bundled_plugins_path, d) for d in Core.storage.list_dir(Core.bundled_plugins_path) if d.endswith('.bundle')}
        else:
            bundled_plugin_paths = {}
        plugin_paths = {d : Core.storage.join_path(self.plugins_path, d) for d in Core.storage.list_dir(self.plugins_path) if d.endswith('.bundle')}

        combine_plugin_paths = dict()
        combine_plugin_paths.update(bundled_plugin_paths)
        combine_plugin_paths.update(plugin_paths)

        for name in combine_plugin_paths.keys():
            bundle = BundleInfo(combine_plugin_paths[name], name).info
            if bundle['ignore']:
                continue

            if bundle['identifier'] in identifiers:
                self.bundle_dict[bundle['identifier']] = {
                    'name': bundle['name'], 'has_services': bundle['has_services'],
                    'bundled': bundle['bundled'], 'path': combine_plugin_paths[name]
                    }
            elif bundle['identifier'] in self.bundle_dict.keys():
                del self.bundle_dict[bundle['identifier']]

class USSInstallService(object):
    def __init__(self, identifier, name, initial_url, update_url):
        Log.Debug("Starting the USS install service")
        self.installing = False
        self.stage = Core.storage.join_path(Core.storage.data_path, 'DataItems', 'Stage')
        self.inactive = Core.storage.join_path(Core.storage.data_path, 'DataItems', 'Deactivated')
        self.plugins_path = Core.storage.join_path(Core.app_support_path, 'Plug-ins')
        self.bundleservice = BundleService()
        self.name = name
        self.update_url = update_url
        self.initial_url = initial_url
        self.identifier = identifier
        self.update_info = dict()
        self.current_info = dict()
        self.host_list = list()
        self.info_from_plist(identifier)

        try:
            Core.storage.remove_tree(self.stage)
        except:
            Log.Error("Unalbe to remove staging root")
        Core.storage.make_dirs(self.stage)

        try:
            Core.storage.remove_tree(self.inactive)
        except:
            Log.Error("Unable to remove inactive root")
        Core.storage.make_dirs(self.inactive)

        if HISTORY_KEY in Dict:
            self.history = Dict[HISTORY_KEY]
        else:
            self.history = list()
        self.history_lock = Thread.Lock()

    def info_record(self, identifier, action, version=None, notes=None):
        info = dict()
        info[IDENTIFIER_KEY] = identifier
        info[DATE_KEY] = Datetime.Now()
        info[ACTION_KEY] = action
        if notes:
            info[NOTES_KEY] = notes
        if version:
            info[VERSION_KEY] = version
        return info

    def add_history_record(self, identifier, action, version=None, notes=None):
        info = self.info_record(identifier, action, version, notes)
        try:
            self.history_lock.acquire()
            self.history.append(info)
            Dict[HISTORY_KEY] = self.history
            Dict.Save()
        finally:
            self.history_lock.release()

    def setup_stage(self, identifier):
        stage_path = Core.storage.join_path(self.stage, identifier)
        Log("Setting up staging area for %s at %s" % (identifier, stage_path))
        Core.storage.remove_tree(stage_path)
        Core.storage.make_dirs(stage_path)
        return stage_path

    def unstage(self, identifier):
        stage_path = Core.storage.join_path(self.stage, identifier)
        Log("Unstaging files for %s (removing %s)" % (identifier, stage_path))
        Core.storage.remove_tree(stage_path)

    def cleanup(self, identifier):
        # Don't delete the old Framework.bundle on Windows, as it will fail because the file is in use
        if identifier == 'com.plexapp.framework' and sys.platform == 'win32':
            return
        inactive_path = Core.storage.join_path(self.inactive, identifier)
        if Core.storage.dir_exists(inactive_path):
            Log("Cleaning up after %s (removing %s)" % (identifier, inactive_path))
            Core.storage.remove_tree(inactive_path)

    def deactivate(self, identifier):
        if identifier in self.bundleservice.bundles:
            bundle = self.bundleservice.bundles[identifier]
            inactive_path = Core.storage.join_path(self.inactive, identifier, bundle['name'])
            self.cleanup(identifier)
            Log("Deactivating an old installation of %s (moving to %s)" % (identifier, inactive_path))
            Core.storage.make_dirs(inactive_path)
            Core.storage.rename(Core.storage.join_path(self.plugins_path, bundle['name']), inactive_path)
            return True
        return False

    def reactivate(self, identifier):
        try:
            if identifier in self.bundleservice.bundles:
                bundle = self.bundleservice.bundles[identifier]
                inactive_path = Core.storage.join_path(self.inactive, identifier, bundle['name'])
                Log("Reactivating the old installation of %s (moving from %s)" % (identifier, inactive_path))
                Core.storage.rename(inactive_path, Core.storage.join_path(self.plugins_path, bundle['name']))
                return True
        except:
            Log.Exception("Unable to reactivate the old installation of %s", identifier)
        return False

    def activate(self, identifier, name, fail_count=0):
        stage_path = Core.storage.join_path(self.stage, identifier)
        final_path = Core.storage.join_path(self.plugins_path, ("%s.bundle" %name if not name.endswith('.bundle') else name))

        if not Core.storage.dir_exists(stage_path):
            Log("Unable to find stage for %s" % identifier)
            return False
        if Core.storage.dir_exists(final_path):
            Log("Plugin named %s.bundle already installed at %s - removing" % (name, final_path))
            Core.storage.remove_tree(final_path)
        Log("Activating a new installation of %s" % identifier)
        try:
            Core.storage.rename(stage_path, final_path)
        except:
            Log.Exception("Unable to activate %s at %s" % (identifier, final_path))
            if fail_count < 5:
                Log.Info("Waiting 2s and trying again")
                Thread.Sleep(2)
                return self.activate(identifier, name, fail_count + 1)
            else:
                Log.Info("Too many failures - returning")
                return False
        return True

    def install_zip_from_url(self, identifier, name, url):
        try:
            archive = Archive.Zip(HTTP.Request(url, cacheTime=0))
        except:
            Log("Unable to download archive for %s" % identifier)
            self.unstage(identifier)
            return False

        if archive.Test() != None:
            Log.Add("The archive of %s is invalid - unable to continue" % identifier)
            self.unstage(identifier)
            return False

        try:
            for archive_name in archive:
                parts = archive_name.split('/')[1:]

                if parts[0] == '' and len(parts) > 1:
                    parts = parts[1:]

                if len(parts) > 1 and parts[0] == 'Contents' and len(parts[-1]) > 0 and parts[-1][0] != '.':
                    stage_path = Core.storage.join_path(self.stage, identifier)
                    file_path = Core.storage.join_path(stage_path, *parts)
                    dir_path = Core.storage.join_path(stage_path, *parts[:-1])

                    if not Core.storage.dir_exists(dir_path):
                        Core.storage.make_dirs(dir_path)
                    Core.storage.save(file_path, archive[archive_name])
                    Log("Extracted %s to %s for %s" % (parts[-1], dir_path, identifier))
                else:
                    Log("Not extracting %s" % archive_name)

        except:
            Log("Error extracting archive of %s" % identifier)
            Log(Plugin.Traceback())
            self.unstage(identifier)
            return False

        finally:
            archive.Close()

        self.deactivate(identifier)
        if not self.activate(identifier, name):
            Log("Unable to activate %s" % identifier)
            if not self.reactivate(identifier):
                Log.Critical("Unable to reactivate %s" % identifier)
            self.unstage(identifier)
            return False

        self.unstage(identifier)
        self.cleanup(identifier)

        return True

    def update_bundle_info(self, identifier, fail_count=0):
        Log("Updating bundle info")
        self.bundleservice.update_bundle_info()
        if identifier not in self.bundleservice.bundles:
            if fail_count < 5:
                Log.Info("Waiting 2s and trying again: Try %i of 5" %fail_count+1)
                Thread.Sleep(2)
                return self.update_bundle_info(identifier, fail_count+1)
            else:
                Log.Info("Too many failures - returning")
            return False
        return True

    def install(self, identifier, name, remoteUrl, action, version=None, notes=None):
        Log("Performing a full installation of %s" % identifier)
        stage_path = self.setup_stage(identifier)

        if not self.install_zip_from_url(identifier, name, remoteUrl):
            return False

        self.add_history_record(identifier, action, version, notes)

        # Check whether this bundle contains services
        if not self.update_bundle_info(identifier):
            Log.Error("Failed to register %s" %identifier)
            return False

        #instruct other plug-ins to reload if necessary
        self.check_if_service_reload_required([identifier])

        # update current_info
        self.info_from_plist(identifier)

        Log("Installation of %s complete" % identifier)
        return True

    def normalize_version(self, version):
        if version[:1] == 'v':
            version = version[1:]
        return version

    def parse_version(self, version):
        try:
            return tuple(map(int, (version.split('.'))))
        except:
            # String comparison by default
            return version

    def info_from_plist(self, identifier):
        if identifier not in self.bundleservice.bundles:
            self.current_info.clear()
            Log("Unable to check update %s because it isn't installed." % identifier)
            return False

        bundle = self.bundleservice.bundles[identifier]
        try:
            plist = Plist.ObjectFromString(Core.storage.load(Core.storage.join_path(self.plugins_path, bundle['name'], 'Contents', 'Info.plist')))
            self.current_info.update({'version': plist[KEY_PLIST_VERSION]})
        except Exception as e:
            Log.Critical(str(e))
            pass

        return bool(self.current_info)

    def check_update(self, identifier):
        try:
            info = JSON.ObjectFromURL(self.update_url, cacheTime=CHECK_INTERVAL, timeout=5)
            version = self.normalize_version(info[KEY_DATA_VERSION])
            remoteUrl = info[KEY_DATA_ZIPBALL]
        except:
            return False

        if identifier not in self.bundleservice.bundles:
            Log("Unable to check update %s because it isn't installed." % identifier)
            return False

        if self.parse_version(version) > self.parse_version(self.current_info['version']):
            self.update_info.update({
                'version': version, 'remoteUrl': remoteUrl,
                'notes': info[KEY_DATA_DESC] if KEY_DATA_DESC in info else ''
                })

        return bool(self.update_info)

    def update(self, identifier):
        if self.check_update(identifier):
            if identifier not in self.bundleservice.bundles:
                Log("Unable to update %s because it isn't installed." % identifier)
                return False

            bundle = self.bundleservice.bundles[identifier]

            if not self.install(identifier, bundle['name'], self.update_info['remoteUrl'], 'Plug-in Updated', version=self.update_info['version'], notes=self.update_info['notes']):
                return False

            # cleanup update_info key
            self.update_info.clear()

            Log("Update of %s complete" % identifier)
            return True
        return False

    def check_if_service_reload_required(self, identifiers):
        """ Check the list of bundle identifiers to see if any of the bundles contain services. If they do, instruct running plug-ins to reload their service list. """
        bundles = self.bundleservice.bundles
        #Log(bundles)
        for ident in identifiers:
            if ident in bundles:
                bundle = bundles[ident]
                #Log(bundle)
                if bundle['has_services']:
                    Log("At least one bundle containing services has been updated - instructing all running plug-ins to reload.")
                    self.reload_services_in_running_plugins()
                    return
        Log("No bundles containing services have been updated.")

    def reload_services_in_running_plugins(self):
        """ Get the list of plug-ins from PMS, and tell any that are running to reload services """
        plugins_list = XML.ElementFromURL('http://127.0.0.1:32400/:/plugins', cacheTime=0)
        for plugin_el in plugins_list.xpath('//Plugin'):
            if str(plugin_el.get('state')) == '0':
                ident = str(plugin_el.get('identifier'))
                if ident != "com.plexapp.plugins.unsupportedservicestools":
                    try:
                        Log("Plug-in %s is currrently running with old service code - reloading", ident)
                        HTTP.Request('http://127.0.0.1:32400/:/plugins/%s/reloadServices' % ident, cacheTime=0, immediate=True)
                    except:
                        Log.Error("Unable to reload services in %s", ident)

        # Reload system services
        Core.services.load()

    def gui_init_install(self):
        action = "Plug-in %s Initial Install" %name
        version = "initial"
        notes = "Initial install of USS"

        if not self.install(self.identifier, self.name, self.initial_url, action, version, notes):
            return "USS initial install faild"

        if not self.info_from_plist(self.identifier):
            return "USS failed to install"

        if not bool(self.current_info):
            return "USS installed but failed to register"

        return "USS installed initial v%s" %self.current_info['version']

    def gui_update(self, check=False):
        if not self.info_from_plist(self.identifier):
            message = "Unable to check update %s because it isn't installed." % self.identifier
            Log(message)
            return message

        if self.identifier not in self.bundleservice.bundles:
            message = "Unable to check update %s because the bundle is not properly register with the server." % self.identifier
            Log(message)
            return message

        if check:
            if not self.check_update(self.identifier):
                return "No Update Available"
            return "v%s Update Available" %self.update_info['version']
        else:
            if not self.update(self.identifier):
                return "Unable to update %s because there is no update." % self.identifier
            return "USS updated to v%s" %self.current_info['version']

    def gui_host_list(self):
        if self.identifier not in self.bundleservice.bundles:
            Log("Unable to retrieve Host list from %s because it cannot be found")
            return False

        bundle = self.bundleservice.bundles[self.identifier]

        plist = Plist.ObjectFromString(Core.storage.load(Core.storage.join_path(bundle['path'], "Contents", "Info.plist")))
        service_dict = Core.services.get_services_from_bundle(bundle['path'], plist)

        if bool(self.host_list):
            self.host_list = list()

        for service_type in service_dict[self.identifier]['ServiceSets']:
            stype = service_dict[self.identifier]['ServiceSets'][service_type]
            if 'URL' in stype.keys():
                for k in stype['URL'].keys():
                    site = stype['URL'][k]
                    if 'URLPatterns' in site.keys():
                        for h in site['URLPatterns']:
                            if not h.startswith('^na'):
                                r = Regex(r'\?(\w+)').search(h)
                                if r:
                                    if r.group(1) not in self.host_list:
                                        self.host_list.append(r.group(1))

        return sorted(self.host_list)
