from bson.objectid import ObjectId

from girder.models.api_key import ApiKey
from girder.models.folder import Folder
from girder.models.file import File
from girder.models.item import Item
from girder.models.user import User
from girder.utility.path import getResourcePath
from girder.utility.path import lookUpPath

import argparse
import glob
import traceback
import subprocess
import shutil
import os
import os.path
import time

# Mount folder via webdav
def mount(api_key, path, folderId, apiUrl):
    print("Mounting %s to %s" % (folderId, path))
    # Mount webdav
    cmd = 'girderfs -c wt_home --api-url %s --api-key %s %s %s ' % (apiUrl, api_key, path, folderId)
    print("Calling: %s", cmd)
    subprocess.call(cmd, shell=True)

# Unmount webdav folder
def unmount(tmpDir):
    print("Unmounting %s" % tmpDir)
    cmd = 'fusermount -u %s' % tmpDir
    subprocess.call(cmd, shell=True)

# Get the list of files from the assetstore
def getFiles(assetstoreId):
    files = list(File().find({
        'assetstoreId': ObjectId(assetstoreId)
    }))
    return files

# Download files from the specified assetstore to temporary location
def downloadFiles(assetstoreId):
    ids = []
    print("Downloading all files from assetstore %s" % assetstoreId)
    files = getFiles(assetstoreId)
    i = 0
    for file in files:
        for user in User().find({'_id': file["creatorId"]}):

            if user['login'] == 'admin':
                continue

            if file['itemId'] is not None:

                item = Item().load(file['itemId'], force=True)
                if item['baseParentType'] != "user":
                    continue

                if 'copied' in file:
                    continue;


                print("Downloading files for user %s" % (user))
                print ("File %s" % file)
                fullpath = getResourcePath("file", file, user=user)
                fullpath = os.path.dirname(fullpath)
                if not fullpath.startswith("/user"):
                    continue

                path = os.path.dirname(fullpath)
                os.makedirs(path, exist_ok=True)
                print("Downloading file %s" % (fullpath))
                for data in File().download(file, headers=False)():
                    f = open(fullpath, "wb")
                    f.write(data)
                    f.close()
                i = i+1
                ids.append(file["_id"])

            else:
                print("Item id is None for %s" % file['_id'])
    print("Downloaded %d of %d files" % (i, len(files)))
    return ids


# Migrate user data
def migrate(user, apiUrl):
    print("\nMigrating data for user %s" % user['login'])

    # Get or create API key for migration
    apiKey = ApiKey().createApiKey(user, 'migration')

    # Look up the "Home" directory
    homeDir = lookUpPath("/user/%s/Home" % user['login'], user=user, test=True)["document"]
    print("Found homeDir %s" % homeDir)

    # Remove old Home, create new (needed for wt_home_dirs)
    print("Removing homeDir")
    Folder().remove(homeDir)
    print("Creating new homeDir")
    newHomeDir = Folder().createFolder(parent=user, name="Home", creator=user, parentType="user")

    # Mount home dir via webdav
    tmpDir = "/tmp/migrate/%s/" % user['login']
    os.makedirs(tmpDir, exist_ok=True)
    print("Created tmpDir %s" % tmpDir)

    mount(apiKey['key'], tmpDir, newHomeDir['_id'], apiUrl)

    # Move Data directory, if present
    print("Moving files")
    try:
        if os.path.exists('/user/%s/Data' % user['login']):
            shutil.move('/user/%s/Data' % user['login'], tmpDir)
        if os.path.exists('/user/%s/Workspace' % user['login']):
            shutil.move('/user/%s/Workspace' % user['login'], tmpDir)
        if os.path.exists('/user/%s/Home' % user['login']):
            for file in glob.glob('/user/%s/Home/*' % user['login']):
                print(file)
                shutil.move(file, tmpDir)
            os.rmdir('/user/%s/Home' % user['login'])
    except Exception as e:
        print("Error moving files: %s"  % str(e))

    time.sleep(60)

    # Unmount
    unmount(tmpDir)

    # Remove tmp folder
    shutil.rmtree(tmpDir)

    # Remove the API key
    ApiKey().remove(apiKey)


def main():
    parser = argparse.ArgumentParser(description='Migrate GridFS to WebDav assetstore.')
    parser.add_argument('-a', '--assetstore', required=True, help='Assetstore ID')
    parser.add_argument('-u', '--url', required=False, default='https://girder.stage.wholetale.org/api/v1',
                        help='Girder API URL')
    args = parser.parse_args()
    print('Using API Server %s' % args.url)
    print('Downloading files from assetstore %s' % args.assetstore)

    # Download files to /user
    downloaded_files = downloadFiles(args.assetstore)
    # Process directories
    print("Processing directories")
    for user_dir in os.listdir("/user"):
        time.sleep(20)
        # There seems to be a race condition with girderfs mounting webdav, rest for a bit
        if dir != 'admin':
            user = next(User().search(user_dir))
            try:
                migrate(user, args.url)
                os.rmdir("/user/%s" % user_dir)
            except Exception as e:
                print("Error migrating %s %s " % (user['login'], str(e)))
                traceback.print_stack()

    # Remove files from GridFS
    print("Removing files from GridFS")
    for file_id in downloaded_files:
        file = File().load(file_id, force=True)
        File().remove(file)

if __name__ == "__main__":
    main()


