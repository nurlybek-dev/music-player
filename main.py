import os
import sys
import json

from PyQt5.Qt import Qt
from PyQt5 import QtWidgets
from PyQt5.QtCore import QAbstractListModel, QObject, QUrl, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtMultimedia import *
from PyQt5.QtMultimediaWidgets import *
from gui import Ui_MainWindow


class Settings:
    SETTINGS_PATH = './userdata.data'
    DEFAULT_PLAYLIST = 'default'
    DEFAULT_PLAYLIST_PATH = './playlists/default.playlist'

    HEIGHT = 500
    FULL_WIDTH = 500
    MAIN_WIDTH = 300
    PLAYLIST_WIDTH = 200

    def __init__(self):
        if not os.path.exists(self.SETTINGS_PATH):
            with open(self.SETTINGS_PATH, 'w+') as f:
                f.write(json.dumps({
                    'default_playlist': self.DEFAULT_PLAYLIST,
                    'opened_playlist': self.DEFAULT_PLAYLIST_PATH
                }))
        
        with open(self.SETTINGS_PATH, 'r') as f:
            data = json.loads(f.read())
            self.default_playlist = data['default_playlist']
            self.opened_playlist = data['opened_playlist']

    def save(self):
        with open(self.SETTINGS_PATH, 'w+') as f:
            f.write(json.dumps({
                'default_playlist': self.default_playlist,
                'opened_playlist': self.opened_playlist
            }))

    def set_opened_playlist(self, playlist):
        self.opened_playlist = playlist
        self.save()


class Playlist:

    BASE_PATH = './playlists/%s.playlist'

    def __init__(self, path = None, name = None):
        self.path = path
        self.name = name
        self.tracks = []
        self.current_track_index = 0

        if self.path:
            self.path = path
            self.name = None
            if not os.path.exists(self.path):
                self.new()
            else:
                self.load()
        elif self.name:
            self.name = name
            self.path = self.BASE_PATH % name
            if not os.path.exists(self.path):
                self.new()
            else:
                self.load()
        else:
            self.path = Settings.DEFAULT_PLAYLIST_PATH
            self.name = Settings.DEFAULT_PLAYLIST
            if not os.path.exists(self.path):
                self.new()
            else:
                self.load()

    def new(self):
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))

        if not self.name:
            basename = os.path.basename(self.path)
            self.name = os.path.splitext(basename)[0]

        self.save()
    
    def add_item(self, item):
        self.tracks.append(item)
        self.save()

    def add_items(self, items):
        self.tracks.extend(items)
        self.save()

    def remove_item(self, index):
        del self.tracks[index]
        self.save()

    def set_current_track_index(self, index):
        self.current_track_index = index
        self.save()

    def save(self):
        with open(self.path, 'w+') as f:
            f.write(json.dumps({
                'name': self.name,
                'tracks': self.tracks,
                'current_track_index': self.current_track_index
            }))

    def load(self):
        with open(self.path) as f:
            data = json.loads(f.read())
            self.name = data['name']
            self.tracks = data['tracks']
            self.current_track_index = data['current_track_index']

class PlaylistModel(QAbstractListModel):
    def __init__(self, playlist, *args, **kwargs):
        super(PlaylistModel, self).__init__(*args, **kwargs)
        self.playlist = playlist

    def data(self, index, role):
        if role == Qt.DisplayRole:
            media = self.playlist.media(index.row())
            return media.canonicalUrl().fileName()
    
    def rowCount(self, index):
        return self.playlist.mediaCount()


class PlaylistEvents(QObject):
    playlist_changed = pyqtSignal(Playlist)


class MediaPlayer:
    SUPPORTED_FORMATS = [
        '.mp3',
        '.wav',
        '.mp4',
    ]

    def __init__(self, playlist) -> None:
        self.__media_player = QMediaPlayer()
        self.__media_playlist = QMediaPlaylist()

        self.__media_player.setPlaylist(self.__media_playlist)

        self.__playlist_model = PlaylistModel(self.__media_playlist)

        self.__playlist = Playlist(path=playlist)
        self.__media_playlist.currentIndexChanged.connect(self.update_playlist_index)
        self.playlist_events = PlaylistEvents()


    def load(self):
        self.__media_player.stop()
        self.__media_playlist.clear()
        for track in self.__playlist.tracks:
            url = QUrl.fromLocalFile(track)
            self.__media_playlist.addMedia(QMediaContent(url))
        self.__media_playlist.setCurrentIndex(self.__playlist.current_track_index)
        self.__playlist_model.layoutChanged.emit()
        self.playlist_events.playlist_changed.emit(self.__playlist)

    def create_playlist(self, name):
        playlist = Playlist(name=name)
        self.change_playlist(playlist)

    def load_playlist(self, path):
        playlist = Playlist(path=path)
        self.change_playlist(playlist)

    def change_playlist(self, playlist):
        self.__playlist = playlist
        self.load()

    def get_model(self):
        return self.__playlist_model

    def isMetaDataAvailable(self):
        return self.__media_player.isMetaDataAvailable()

    def metaData(self, key):
        return self.__media_player.metaData(key)

    def set_current_index(self, index):
        self.__media_playlist.setCurrentIndex(index)

    def update_playlist_index(self, index):
        self.__playlist.set_current_track_index(index)

    def play(self):
        self.__media_player.play()

    def pause(self):
        self.__media_player.pause()

    def stop(self):
        self.__media_player.stop()

    def next(self):
        self.__media_playlist.next()

    def prev(self):
        self.__media_playlist.previous()

    def remove_media(self, index):
        self.__media_playlist.removeMedia(index)
        self.__playlist.remove_item(index)

    def add_media(self, file):
        extension = os.path.splitext(file)[1]
        if extension not in self.SUPPORTED_FORMATS:
            return False
        url = QUrl.fromLocalFile(file)
        self.__media_playlist.addMedia(QMediaContent(url))
        self.__playlist_model.layoutChanged.emit()
        self.__playlist.add_item(file)
        return True

    def duration_changed_connect(self, function):
        return self.__media_player.durationChanged.connect(function)

    def position_changed_connect(self, function):
        return self.__media_player.positionChanged.connect(function)

    def metadata_changed_connect(self, function):
        return self.__media_player.metaDataChanged.connect(function)

    def current_index_changed_connect(self, function):
        self.__media_playlist.currentIndexChanged.connect(function)

    def connect_volume_slider(self, volume_slider):
        volume_slider.valueChanged.connect(self.__media_player.setVolume)

    def connect_time_slider(self, time_slider):
        time_slider.valueChanged.connect(self.__media_player.setPosition)


class Application(QtWidgets.QMainWindow):

    def __init__(self):
        super(Application, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.settings = Settings()
        self._media_player = MediaPlayer(self.settings.opened_playlist)
        self.is_playlist_tab_open = False

        self.ui.play_button.clicked.connect(self._media_player.play)
        self.ui.pause_button.clicked.connect(self._media_player.pause)
        self.ui.stop_button.clicked.connect(self._media_player.stop)
        self.ui.next_button.clicked.connect(self._media_player.next)
        self.ui.prev_button.clicked.connect(self._media_player.prev)

        self.ui.action_new.triggered.connect(self.new_playlist)
        self.ui.action_open.triggered.connect(self.open_playlist)

        self.ui.action_add_track.triggered.connect(self.add_file)
        self.ui.action_add_folder.triggered.connect(self.add_folder)

        self.ui.playlist_button.clicked.connect(self.playlist_toggle)
        self.ui.playlist.doubleClicked.connect(self.on_playlist_dbl_clicked)

        self.ui.playlist.setModel(self._media_player.get_model())

        self.ui.playlist.setContextMenuPolicy(Qt.ActionsContextMenu)
        remove_action = QtWidgets.QAction("Remove", self)
        remove_action.triggered.connect(self.remove_media)
        self.ui.playlist.addAction(remove_action)

        self._media_player.current_index_changed_connect(self.playlist_position_changed)

        self._media_player.duration_changed_connect(self.update_duration)
        self._media_player.position_changed_connect(self.update_position)
        self._media_player.metadata_changed_connect(self.update_metadata)

        self._media_player.connect_volume_slider(self.ui.volume_slider)
        self._media_player.connect_time_slider(self.ui.time_slider)

        self._media_player.playlist_events.playlist_changed.connect(self.playlist_changed)

        self._media_player.load()

    def add_file(self):
        filenames, ok = QtWidgets.QFileDialog.getOpenFileNames(self, 'Select files', '', 'mp3 Audio (*.mp3);;All files (*.*)')
        if ok:
            for file in filenames:
                self._media_player.add_media(file)

    def add_folder(self):
        dialog = QtWidgets.QFileDialog()
        folder = dialog.getExistingDirectory(self, 'Select folder')
        for dirpath, dirnames, filenames in os.walk(folder):
            for file in filenames:
                self._media_player.add_media(os.path.join(dirpath, file))

    def new_playlist(self):
        playlist_name, ok = QtWidgets.QInputDialog().getText(self, 'Playlist name', 'Enter new playlist name')
        if ok:
            self._media_player.create_playlist(playlist_name)

    def open_playlist(self):
        playlist_path, ok = QtWidgets.QFileDialog.getOpenFileName(self, 'Select playlist', './playlists', '*.playlist')
        if ok:
            self._media_player.load_playlist(playlist_path)

    def playlist_changed(self, playlist):
        self.settings.set_opened_playlist(playlist.path)
        self.ui.playlist_name_label.setText(playlist.name)

    def playlist_toggle(self):
        if not self.is_playlist_tab_open:
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

        self.is_playlist_tab_open = not self.is_playlist_tab_open

    def remove_media(self):
        index = self.ui.playlist.currentIndex().row()
        self._media_player.remove_media(index)

    def on_playlist_dbl_clicked(self):
        index = self.ui.playlist.currentIndex().row()
        self._media_player.set_current_index(index)
        self._media_player.play()

    def update_duration(self, duration):
        self.ui.time_slider.setMaximum(duration)

        if duration >= 0:
            self.ui.current_time_label.setText('00:00/%s' % self.format_time(duration))

    def update_position(self, position):
        if position >= 0:
            max_time = self.ui.current_time_label.text()[6:]
            self.ui.current_time_label.setText('%s/%s' % (self.format_time(position), max_time))

        self.ui.time_slider.blockSignals(True)
        self.ui.time_slider.setValue(position)
        self.ui.time_slider.blockSignals(False)

    def format_time(self, ms):
        s = round(ms / 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return "%02d:%02d" % (m, s)

    def update_metadata(self):
        if self._media_player.isMetaDataAvailable():
            album_title = self._media_player.metaData(QMediaMetaData.AlbumTitle)
            title = self._media_player.metaData(QMediaMetaData.Title)
            album_artist = self._media_player.metaData(QMediaMetaData.AlbumArtist)
            image = self._media_player.metaData(QMediaMetaData.ThumbnailImage)

            try:
                self.ui.cover_label.setPixmap(QPixmap.fromImage(image).scaled(278, 268, Qt.KeepAspectRatio))
                self.ui.title_label.setText(f'{album_title} - {title}')
                self.ui.artist_label.setText(f'{album_artist}')
            except TypeError:
                pass
        else:
            qb = QPixmap()
            qb.load('no-photo.png')
            self.ui.cover_label.setPixmap(qb.scaled(278, 268, Qt.KeepAspectRatio))
            self.ui.title_label.setText('No data')
            self.ui.artist_label.setText('No data')

    def playlist_position_changed(self, i: int):
        if i > -1:
            ix = self._media_player.get_model().index(i)
            self.ui.playlist.setCurrentIndex(ix)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    application = Application()
    application.show()

    sys.exit(app.exec())
