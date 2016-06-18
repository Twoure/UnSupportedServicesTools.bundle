#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Plex Plugin Updater
# $Id$
#
# Universal plugin updater module for Plex Server Channels that
# implement automatic plugins updates from remote config.
# Support Github API by default
#
# https://github.com/kolsys/plex-channel-updater
#
# Copyright (c) 2014, KOL
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# UnSupportedServices Updater
# Edited by: Twoure
# Date: 06/11/2016

KEY_PLIST_VERSION = 'CFBundleVersion'
KEY_PLIST_URL = 'PlexPluginVersionUrl'

KEY_DATA_VERSION = 'tag_name'
KEY_DATA_DESC = 'body'
KEY_DATA_ZIPBALL = 'zipball_url'

CHECK_INTERVAL = CACHE_1HOUR * 12


class USSUpdater:
    info = None
    update = None

    def __init__(self):
        if self.IsInstalled():
            if self.InitBundleInfo():
                if self.IsUpdateAvailable():
                    self.DoUpdate()
                    Log.Debug('* USS Updated to %s' %str(self.update['verion']))
                    Log.Debug('* USS Update Info %s' %self.update['info'])
                else:
                    Log.Debug('* USS is up-to-date: v%s' %str(self.info['version']))
            else:
                Log.Error('* USS Error: InitBundleInfo() failed')
        else:
            Log.Debug('* USS Not Yet Installed. Installing new USS.')
            self.InitInstall()

    def NormalizeVersion(self, version):
        if version[:1] == 'v':
            version = version[1:]
        return version

    def ParseVersion(self, version):
        try:
            return tuple(map(int, (version.split('.'))))
        except:
            # String comparison by default
            return version

    def IsUpdateAvailable(self):
        try:
            info = JSON.ObjectFromURL(self.info['url'], cacheTime=CHECK_INTERVAL, timeout=5)
            version = self.NormalizeVersion(info[KEY_DATA_VERSION])
            dist_url = info[KEY_DATA_ZIPBALL]
        except:
            return False

        if self.ParseVersion(version) > self.ParseVersion(self.info['version']):
            self.update = {
                'version': version, 'url': dist_url,
                'info': info[KEY_DATA_DESC] if KEY_DATA_DESC in info else ''
                }

        return bool(self.update)

    def InitBundleInfo(self):
        try:
            plist = Plist.ObjectFromString(
                Core.storage.load(
                    Core.storage.join_path(self.BundlePath(), 'Contents', 'Info.plist')
                    )
                )
            self.info = {
                'version': plist[KEY_PLIST_VERSION],
                'url': plist[KEY_PLIST_URL]
                }
        except Exception as e:
            Log.Critical(str(e))
            pass

        return bool(self.info)

    def IsInstalled(self):
        return Core.storage.dir_exists(self.BundlePath())

    def BundlePath(self):
        return Core.storage.abs_path(
            Core.bundle_path.replace('lmwt-kiss.bundle', 'UnSupportedServices.bundle')
            )

    def InitInstall(self):
        dist_url = 'https://api.github.com/repos/Twoure/UnSupportedServices.bundle/zipball/master'
        self.update = {'url': dist_url, 'version': 'initial install version'}
        self.DoUpdate()
        return

    def DoUpdate(self):
        try:
            bundle_path = self.BundlePath()
            if Core.storage.dir_exists(bundle_path):
                for item in Core.storage.list_dir(bundle_path):
                    item_path = Core.storage.join_path(bundle_path, item)
                    try:
                        if Core.storage.dir_exists(item_path):
                            Core.storage.remove_tree(item_path)
                        elif Core.storage.file_exists(item_path):
                            Core.storage.remove(item_path)
                    except Exception as e:
                        Log.Error('* USS DoUpdate Error #1: %s' %str(e))
            else:
                Core.storage.ensure_dirs(bundle_path)

            zip_data = Archive.ZipFromURL(self.update['url'])

            for name in zip_data.Names():
                data = zip_data[name]
                parts = name.split('/')
                shifted = Core.storage.join_path(*parts[1:])
                full = Core.storage.join_path(bundle_path, shifted)

                if '/.' in name:
                    continue

                if name.endswith('/'):
                    Core.storage.ensure_dirs(full)
                else:
                    Core.storage.save(full, data)
            del zip_data

            Log.Debug('* USS sucessfully installed: %s' %str(self.update['version']))

            return
        except Exception as e:
            Log.Error('* USS DoUpdate Error #2: %s' %str(e))
            return
