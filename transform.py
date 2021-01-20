# -*- coding:utf-8 -*-
# TODO: Access the musicbrainz database and obtain tags for the new mp3 files

import os
import re
from getpass import getuser

# Modules for accessing online files
import asyncio
import aiohttp
import aiofiles

# Modules for logging and parsing config.ini data
import logging
import logging.config
import configparser

# Modules for writing metadata tags
from PIL import Image
from io import BytesIO
from urllib.request import urlopen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from mutagen.easyid3 import EasyID3

def process(s):
    '''Process the filename as input string s to ensure that it adheres to Windows file naming requirements.'''
    if len(s) > 240: s = s[0,240]
    return ''.join(re.split('[\\/:"*?<>|]+', s.strip()))

def affix_tags(filename, song_info):
    '''Write tags contained in the tuple song_info to the mp3 file with name filename.'''
    song_name, singer, album, track_number, disc_number, album_art = song_info
    logger.info(f"Writing metadata for song \"{song_name}\".")

    metadata = MP3(filename, ID3=EasyID3)
    metadata['title'] = song_name
    metadata['artist'] = singer
    metadata['album'] = album
    metadata['albumartist'] = singer
    metadata['discnumber'] = disc_number
    metadata['tracknumber'] = str(track_number)
    metadata.save()

    ima=Image.open(album_art)
    with BytesIO() as f:
        ima.save(f, format='PNG')
        f.seek(0)
        ima_png = f.getvalue()

    id3_metadata = ID3(filename)
    id3_metadata.delall('APIC')
    id3_metadata['APIC'] = APIC(encoding=3, mime='image/png', type=3, desc=u'Cover', data=ima_png)
    id3_metadata.save()
    logger.info(f"Tags affixed for song \"{song_name}\".")

class Transform():
    def __init__(self):
        self.uc_path = ''
        self.mp3_path = ''
        self.id2file = {}  # {mp3 ID: file name}

    def check_config(self):
        '''Parse the config.ini file, locate paths for the folders for the cached audio data and for the generated mp3 files. Check if there are any errors with the path name or location.'''
        config = configparser.ConfigParser()
        config.read('config.ini')

        if 'cache' in config['path']:
            self.uc_path = os.path.normpath(config['path']['cache'])
            logger.info(f"Located cache directory at {self.uc_path}.")
        else:
            self.uc_path = "C:\\Users\\%s\\AppData\\Local\\Netease\\CloudMusic\\Cache\\Cache\\" % getuser()
            logger.warning(
                f"Failed to read cache path from config.ini. Using default value at {self.uc_path} instead.")
        if 'mp3' in config['path']:
            self.mp3_path = os.path.normpath(config['path']['mp3'])
            logger.info(f"Located audio storage directory at {self.mp3_path}.")
        else:
            self.mp3_path = "C:\\Users\\%s\\Desktop\\" % getuser()
            logger.warning(
                f"Failed to read cache path from config.ini. Using default value at {self.mp3_path} instead.")

        if not os.path.exists(self.uc_path):
            logger.critical("Bad cache directory. Exiting...", exc_info=True)
            return False
        if not os.path.exists(self.mp3_path):
            logger.warning(f"Path for storing mp3 file dos not exist. New directory {self.mp3_path} generated.", exc_info=False)
            os.mkdir(self.mp3_path)
            return True 

        # 容错处理 防止绝对路径结尾不是\\
        if self.uc_path[-1] != '\\':
            self.uc_path += '\\'
        if self.mp3_path[-1] != '\\':
            self.mp3_path += '\\'
        return True

    def generate_files(self):
        files = os.listdir(self.uc_path)
        for file in files:
            if file[-3:] == '.uc':  # 后缀uc结尾为歌曲缓存
                song_id = self.get_song_by_file(file)
                if not song_id:
                    continue
                self.id2file[song_id] = self.uc_path + file
        logger.info("Files generated.")

    def on_transform(self):
        loop = asyncio.get_event_loop()
        tasks = [self.do_transform(song_id, file) for song_id, file in self.id2file.items()]
        loop.run_until_complete(asyncio.wait(tasks))
        loop.close()

    async def do_transform(self, song_id, uc_file):
        logger.info("Transformation started.")
        song_info = await self.get_song_info(song_id)
        song_name = process(song_info[0])
        singer = process(song_info[1])
        async with aiofiles.open(uc_file, mode='rb') as f:
            uc_content = await f.read()
            mp3_content = bytearray()
            logger.debug("Byte transcode started")
            for byte in uc_content:
                byte ^= 0xa3
                mp3_content.append(byte)

            mp3_file_name = self.mp3_path + '%s - %s.mp3' % (singer, song_name)
            async with aiofiles.open(mp3_file_name, 'wb') as mp3_file:
                await mp3_file.write(mp3_content)
                logger.info(f"Transformation success for file {mp3_file_name}")

            try: # To prevent Visual Studio runtime issues
                affix_tags(mp3_file_name, song_info)
            except Exception as e:
                logger.error(f"Error writing metadata tags for file {mp3_file_name}. Details: \n {e}",
                            exc_info=False)

    def get_song_by_file(self, file_name):
        # -前面的数字是歌曲ID，例：1347203552-320-0aa1
        match_inst = re.match('\d*', file_name)  
        if match_inst:
            return match_inst.group()

    async def get_song_info(self, song_id):
        '''Access the NetEase CloudMusic API to fetch tags and album arts for the song with the numerical id song_id. A sample URL to the API takes the form of https://api.imjad.cn/cloudmusic/?type=detail&id=1347203552.'''
        try:
            url = 'https://api.imjad.cn/cloudmusic/?type=detail&id={}'.format(song_id) 
            logger.info(f"Began lookup for song info on {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    jsons = await response.json(content_type=None)
                    song_name = jsons['songs'][0]['name']
                    singer = jsons['songs'][0]['ar'][0]['name']
                    album = jsons['songs'][0]['al']['name']
                    track_number = jsons['songs'][0]['no']
                    disc_number = jsons['songs'][0]['cd']
                    album_art = urlopen(jsons['songs'][0]['al']['picUrl'])
                    logger.debug("Found the following metadata for the song...")
                    logger.debug(f"\t song_name: {song_name}")
                    logger.debug(f"\t singer: {singer}")
                    logger.debug(f"\t album: {album}")
                    logger.debug(f"\t track_number: {track_number}")
                    logger.debug(f"\t disc_number: {disc_number}")
                    logger.debug(f"\t album_art: {album_art}")
                    return (song_name, singer, album, track_number, disc_number, album_art)
        except Exception as e:
            logger.error(f"Song info not found. Details: \n {e}", exc_info=False)
            return (song_id, 'Unknown', 'Unknown', '0', '0', None)

if __name__ == '__main__':
    logging.config.fileConfig("config.ini")
    logger = logging.getLogger("root")

    logger.info("Program started.")
    transform = Transform()
    if not transform.check_config(): exit()
    transform.generate_files()
    transform.on_transform()
    logger.info("All Actions Complete!")
    