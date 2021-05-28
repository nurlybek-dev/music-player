import os
import sys
import json
from typing import Set

from PyQt5.Qt import Qt
from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap
from gui import Ui_MainWindow
from pygame import mixer
import mutagen


class Settings:
    SETTINGS_PATH = './userdata.data'
    DEFAULT_PLAYLIST = './playlists/default.playlist'
    SUPPORTED_FORMATS = [
        '.mp3',
        '.wav',
        '.flac'
        '.mp4',
        '.asf',
        '.ogg',
        '.aiff',
        '.aac',
        '.wma',
        '.alac'
    ]

    HEIGHT = 500
    FULL_WIDTH = 500
    MAIN_WIDTH = 300
    PLAYLIST_WIDTH = 200

    def __init__(self):
        if not os.path.exists(self.SETTINGS_PATH):
            with open(self.SETTINGS_PATH, 'w+') as f:
                f.write(json.dumps({
                    'default_playlist': self.DEFAULT_PLAYLIST,
                    'opened_playlist': self.DEFAULT_PLAYLIST,
                    'current_track': 0
                }))
        
        with open(self.SETTINGS_PATH, 'r') as f:
            data = json.loads(f.read())
            self.default_playlist = data['default_playlist']
            self.opened_playlist = data['opened_playlist']
            self.current_track = data['current_track']

    def save(self):
        with open(self.SETTINGS_PATH, 'w+') as f:
            f.write(json.dumps({
                'default_playlist': self.default_playlist,
                'opened_playlist': self.opened_playlist,
                'current_track': self.current_track
            }))

    def set_track(self, track):
        self.current_track = track
        self.save()

    def set_opened_playlist(self, playlist):
        self.opened_playlist = playlist.path
        self.save()


class Track(object):
    def __init__(self, path):

        self.title = 'Unknown'
        self.artist = 'Unknown'
        self.length = 0
        self.bitrate = 0
        self.cover = None
        audio = mutagen.File(path)

        if not audio:
            print("Audio not found:", path)
        else:
            self.path = path
            if 'TIT2' in audio.tags:
                self.title = audio.tags['TIT2'].text[0]
            if 'TPE1' in audio.tags:
                self.artist = audio.tags['TPE1'].text[0]
            if 'TALB' in audio.tags:
                self.album = audio.tags['TALB'].text[0]
            if 'APIC:' in audio.tags:
                self.cover = audio.tags['APIC:']

            self.sample_rate = audio.info.sample_rate
            self.length = audio.info.length
            self.bitrate = audio.info.bitrate

    def get_bitrate(self):
        bps = self.bitrate
        kbps = bps // 1000
        if kbps > 0:
            return f'{kbps}kbps'
        else:
            return f'{bps}bps'

    def get_length(self):
        length = self.length
        minutes = int(length // 60)
        seconds = int(length) - (minutes * 60)
        return f'{minutes}:{seconds}'

    def get_cover_image(self):
        qb = QPixmap()
        if self.cover:
            qb.loadFromData(self.cover.data)
        else:        
            qb.load('no-photo.png')
        return qb
        

class PlaylistItemWidget(QtWidgets.QWidget):
    def __init__(self, path, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.vbox = QtWidgets.QVBoxLayout()
        self.track = Track(path)
        self.top_label = QtWidgets.QLabel(f'{self.track.artist}-{self.track.title}')
        self.bottom_label = QtWidgets.QLabel(f'{self.track.get_length()}')
        self.vbox.addWidget(self.top_label)
        self.vbox.addWidget(self.bottom_label)
        self.setLayout(self.vbox)


class Playlist:

    def __init__(self, path, widget):
        self.path = path
        self.widget = widget
        self.tracks = []
        self.current_track = 0

        if not os.path.exists(path):
            self.new()
        else:
            self.load()

    def new(self):
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))

        basename = os.path.basename(self.path)
        self.name = os.path.splitext(basename)[0]

        self.save()

    def load(self):
        with open(self.path) as f:
            data = json.loads(f.read())
            self.name = data['name']
            self.tracks = data['tracks']
        
        self.populate_list()

    def add_items(self, items):
        self.tracks.extend(items)
        self.populate_list(items=items, clear=False)
        self.save()

    def populate_list(self, items=None, clear=True):
        if clear:
            self.widget.clear()

        tracks = items if items else self.tracks
        for track in tracks:
            self.add_track_to_widget(track)

    def add_track_to_widget(self, track):
        widget = PlaylistItemWidget(track)
        item = QtWidgets.QListWidgetItem(self.widget)
        item.setSizeHint(widget.sizeHint())
        self.widget.addItem(item)
        self.widget.setItemWidget(item, widget)

    def remove(self, index):
        del self.tracks[index]
        self.widget.takeItem(index)
        self.save()

    def save(self):
        with open(self.path, 'w+') as f:
            f.write(json.dumps({
                'name': self.name,
                'tracks': self.tracks
            }))


class Application(QtWidgets.QMainWindow):
    """
    TODO: Async add files
    """

    def __init__(self):
        super(Application, self).__init__()
        mixer.init()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.settings = Settings()
        self.playlist = Playlist(self.settings.opened_playlist, self.ui.playlist)
        self.is_playing = False
        self.is_paused = False
        self.current_track = False
        self.is_playlist_open = False
        self.pos_changed = False

        self.ui.play_button.clicked.connect(self.play)
        self.ui.pause_button.clicked.connect(self.pause)
        self.ui.stop_button.clicked.connect(self.stop)
        self.ui.next_button.clicked.connect(self.next)
        self.ui.prev_button.clicked.connect(self.prev)

        self.ui.action_new.triggered.connect(self.new_playlist)
        self.ui.action_open.triggered.connect(self.open_playlist)

        self.ui.action_add_track.triggered.connect(self.add_file)
        self.ui.action_add_folder.triggered.connect(self.add_folder)

        self.ui.playlist_button.clicked.connect(self.playlist_toggle)
        self.ui.playlist.setContextMenuPolicy(Qt.ActionsContextMenu)
        remove_action = QtWidgets.QAction("Remove", self)
        remove_action.triggered.connect(self.remove)
        self.ui.playlist.addAction(remove_action)
        self.ui.playlist.doubleClicked.connect(self.play)
        self.ui.playlist.setCurrentRow(self.settings.current_track)

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)

        self.ui.volume_slider.valueChanged.connect(self.volume_changed)
        mixer.music.set_volume(self.ui.volume_slider.value() / 100)
        self.change_playlist(self.playlist)
        self.select_track()

    def add_file(self):
        filenames, ok = QtWidgets.QFileDialog.getOpenFileNames(self, 'Select files')
        if ok:
            files = []
            for file in filenames:
                extension = os.path.splitext(file)[1]
                if extension not in Settings.SUPPORTED_FORMATS:
                    continue
                files.append(file)

            self.playlist.add_items(files)

    def add_folder(self):
        dialog = QtWidgets.QFileDialog()
        folder = dialog.getExistingDirectory(self, 'Select folders')
        files = []
        for dirpath, dirnames, filenames in os.walk(folder):
            for file in filenames:
                extension = os.path.splitext(file)[1]
                if extension not in Settings.SUPPORTED_FORMATS:
                    continue
                files.append(os.path.join(dirpath, file))

        self.playlist.add_items(files)

    def new_playlist(self):
        playlist_name, ok = QtWidgets.QInputDialog().getText(self, 'Playlist name', 'Enter new playlist name')
        if ok:
            playlist_path = f'./playlists/{playlist_name}.playlist'
            playlist = Playlist(playlist_path, self.ui.playlist)
            self.change_playlist(playlist)

    def open_playlist(self):
        playlist_path, ok = QtWidgets.QFileDialog.getOpenFileName(self, 'Select playlist', './playlists', '*.playlist')
        if ok:
            playlist = Playlist(playlist_path, self.ui.playlist)
            self.change_playlist(playlist)

    def change_playlist(self, playlist):
        mixer.music.stop()
        mixer.music.unload()

        self.playlist = playlist
        self.ui.playlist_name_label.setText(self.playlist.name)

        self.settings.set_opened_playlist(self.playlist)

    def playlist_toggle(self):
        if not self.is_playlist_open:
            self.ui.playlist_frame.setMinimumWidth(Settings.PLAYLIST_WIDTH)
            self.ui.centralwidget.setMinimumWidth(Settings.FULL_WIDTH)

            self.setMinimumWidth(Settings.FULL_WIDTH)
            self.setMaximumWidth(Settings.FULL_WIDTH)
            self.resize(Settings.FULL_WIDTH, Settings.HEIGHT)
        else:
            self.ui.playlist_frame.setMinimumWidth(0)
            self.ui.centralwidget.setMinimumWidth(Settings.MAIN_WIDTH)
            
            self.setMinimumWidth(Settings.MAIN_WIDTH)
            self.setMaximumWidth(Settings.FULL_WIDTH)
            self.resize(Settings.MAIN_WIDTH, Settings.HEIGHT)

        self.is_playlist_open = not self.is_playlist_open

    def select_track(self):
        track = self.selected_track()
        if not track:
            mixer.music.stop()
            return None

        if self.current_track != track:
            self.current_track = track
            self.ui.cover_label.setPixmap(track.get_cover_image())
            self.ui.title_label.setText(track.title)
            self.ui.artist_label.setText(track.artist)
            self.ui.track_progress.setMaximum(int(track.length * 1000))
            self.settings.set_track(self.ui.playlist.currentRow())
            mixer.music.load(track.path)
        
        return track

    def play(self):
        track = self.select_track()
        if track:
            if self.is_paused:
                mixer.music.unpause()
                self.is_paused = False
                self.is_playing = True
            else:
                mixer.music.play()
                self.is_playing = True

    def pause(self):
        if self.is_playing and not self.is_paused:
            mixer.music.pause()
            self.is_playing = False
            self.is_paused = True
        else:
            mixer.music.unpause()
            self.is_playing = True
            self.is_paused = False

    def stop(self):
        mixer.music.stop()
        self.is_playing = False
        self.is_paused = False

    def remove(self):
        current_row = self.ui.playlist.currentRow()
        self.playlist.remove(current_row)

    def next(self):
        self.select_item(1)
        self.play()

    def prev(self):
        self.select_item(-1)
        self.play()

    def select_item(self, offset):
        count = self.ui.playlist.count()
        row = self.ui.playlist.currentRow() + offset
        if row >= count:
            row = 0
        elif row < 0:
            row = count - 1
        
        self.ui.playlist.setCurrentRow(row)

    def selected_track(self):
        item = self.ui.playlist.currentItem()
        widget_item = self.ui.playlist.itemWidget(item)
        if widget_item:
            return widget_item.track
        
        return None

    def volume_changed(self, volume):
        mixer.music.set_volume(volume / 100)

    def tick(self):
        pos = mixer.music.get_pos()

        if pos == -1 and self.is_playing:
            self.next()

        if self.is_playing:
            if self.pos_changed:
                self.pos_changed = False
            else:
                self.ui.track_progress.setValue(pos)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    application = Application()
    application.show()

    sys.exit(app.exec())
