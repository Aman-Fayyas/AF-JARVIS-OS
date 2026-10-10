"""Native GTK3 control desktop. All IPC and inference run off the GTK thread."""
from pathlib import Path
import argparse
import json
import os
import queue
import threading
import time
import urllib.parse
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio, Gdk
from . import ipc
from .config import atomic_write, secure_read
from .voice import speak, transcribe

CSS = b'''
label { color: #dae6f4; }
window { background: #080f1c; color: #dae6f4; }
notebook, notebook > stack, list, row, dialog { background: #080f1c; color: #dae6f4; }
notebook tab label { color: #dae6f4; }
headerbar { background: #101c2c; color: #ecf9ff; border-bottom: 1px solid #214357; }
label.title { font-size: 26px; font-weight: bold; color: #72e5ff; }
label.metric { font-size: 18px; color: #8ddfff; }
label.muted { color: #9bafc3; }
button { background: #14283b; color: #d9f4ff; border: 1px solid #28506a; border-radius: 6px; padding: 8px; }
button:hover { background: #22445b; }
button:disabled { color: #728292; }
entry, textview, textview text { background: #0b1726; color: #e2edf8; caret-color: #72e5ff; }
entry { padding: 10px; border: 1px solid #28506a; border-radius: 6px; }
notebook header { background: #101c2c; }
notebook tab { padding: 8px 15px; }
frame { border: 1px solid #214357; border-radius: 7px; }
'''


def button(label, callback):
    item = Gtk.Button(label=label)
    item.connect('clicked', callback)
    return item


def box(vertical=True, spacing=10):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)


def scroll(child):
    pane = Gtk.ScrolledWindow()
    pane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    pane.add(child)
    return pane


class Desktop(Gtk.Window):
    def __init__(self):
        super().__init__(title='AF JARVIS OS • Control Node')
        self.set_default_size(1100, 740)
        self.connect('destroy', self.close)
        settings = Gtk.Settings.get_default()
        settings.set_property('gtk-application-prefer-dark-theme', True)
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.config = {}
        self.conversation = None
        self.generation = None
        self.running = False
        self.last_prompt = ''
        self.last_answer = ''
        self.node_state = {}
        self.messages = queue.Queue(maxsize=4096)
        self.drain_pending = False
        self.drain_lock = threading.Lock()
        self.closed = False
        self.status_busy = False
        self.recording = False
        self.probe_at = 0
        self.settings_loaded = False
        self.favorites = []
        self.recents = []
        self.launch_file = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'af-jarvis/launcher.json'
        try:
            saved = json.loads(secure_read(self.launch_file))
            self.favorites = saved.get('favorites', [])[:30]
            self.recents = saved.get('recents', [])[:12]
        except (OSError, ValueError):
            pass
        header = Gtk.HeaderBar(title='AF JARVIS OS', subtitle='v0.1 Alpha • lightweight control node')
        header.set_show_close_button(True)
        header.pack_end(button('Files', lambda *_: self.launch_named('pcmanfm.desktop')))
        header.pack_end(button('Terminal', lambda *_: self.launch_named('xterm.desktop')))
        self.set_titlebar(header)
        root = box()
        root.set_border_width(16)
        self.add(root)
        top = box(False)
        brand = Gtk.Label(label='J A R V I S', xalign=0)
        brand.get_style_context().add_class('title')
        top.pack_start(brand, True, True, 0)
        self.connection = Gtk.Label(label='Connecting to Core…')
        top.pack_end(self.connection, False, False, 0)
        root.pack_start(top, False, False, 0)
        self.notebook = Gtk.Notebook()
        root.pack_start(self.notebook, True, True, 0)
        self.make_dashboard()
        self.make_assistant()
        self.make_apps()
        self.make_history()
        self.make_memory()
        self.make_settings()
        self.make_search()
        self.notice = Gtk.Label(label='Offline system commands remain available. Configure an AI Node in Settings.', xalign=0)
        self.notice.set_line_wrap(True)
        self.notice.get_style_context().add_class('muted')
        root.pack_end(self.notice, False, False, 0)
        self.show_all()
        GLib.timeout_add_seconds(5, self.status)
        self.status()

    def page(self, title, content):
        content.set_border_width(14)
        self.notebook.append_page(content, Gtk.Label(label=title))

    def worker(self, request, callback=None):
        def work():
            try:
                for event in ipc.events(request):
                    while not self.closed:
                        try:
                            self.enqueue(callback or self.handle_event, event)
                            break
                        except queue.Full:
                            continue
            except Exception as error:
                event = {'type': 'error', 'message': str(error) if isinstance(error, (ValueError, RuntimeError)) else 'Core unavailable. Desktop applications remain usable.'}
                if not self.closed:
                    self.enqueue(callback or self.handle_event, event)
            finally:
                if request['method'] == 'chat' and not self.closed:
                    self.enqueue(self.chat_finished, {})
        threading.Thread(target=work, daemon=True).start()

    def enqueue(self, callback, event):
        self.messages.put((callback, event), timeout=0.2)
        with self.drain_lock:
            if not self.drain_pending:
                self.drain_pending = True
                GLib.idle_add(self.drain)

    def drain(self):
        if self.closed:
            return False
        tokens = []
        for _ in range(512):
            try:
                callback, event = self.messages.get_nowait()
            except queue.Empty:
                break
            if callback == self.handle_event and event.get('type') == 'token':
                tokens.append(event['text'])
            else:
                if tokens:
                    self.append(''.join(tokens))
                    self.last_answer += ''.join(tokens)
                    tokens.clear()
                callback(event)
        if tokens:
            self.append(''.join(tokens))
            self.last_answer += ''.join(tokens)
        with self.drain_lock:
            if self.messages.empty():
                self.drain_pending = False
                return False
        return True

    def make_dashboard(self):
        page = box()
        self.clock = Gtk.Label(xalign=0)
        self.clock.get_style_context().add_class('title')
        page.pack_start(self.clock, False, False, 5)
        grid = Gtk.Grid(column_spacing=24, row_spacing=18)
        self.metrics = {}
        for n, title in enumerate(['CPU', 'RAM', 'Storage', 'Battery', 'Network', 'Internet', 'Local AI', 'Cloud']):
            card = Gtk.Frame(label=title)
            label = Gtk.Label(label='—', xalign=0)
            label.set_margin_start(16)
            label.set_margin_end(16)
            label.set_margin_top(16)
            label.set_margin_bottom(16)
            label.set_line_wrap(True)
            label.get_style_context().add_class('metric')
            card.add(label)
            card.set_hexpand(True)
            grid.attach(card, n % 2, n // 2, 1, 1)
            self.metrics[title] = label
        page.pack_start(grid, False, False, 0)
        quick = box(False)
        for name, target in [('Browser', 'firefox-esr.desktop'), ('Files', 'pcmanfm.desktop'), ('Terminal', 'xterm.desktop')]:
            quick.pack_start(button(name, lambda _, t=target: self.launch_named(t)), False, False, 0)
        quick.pack_start(button('Ask JARVIS', lambda *_: self.notebook.set_current_page(1)), False, False, 0)
        page.pack_start(quick, False, False, 10)
        self.activity = Gtk.Label(label='Ready for local work.', xalign=0)
        self.activity.set_line_wrap(True)
        page.pack_start(self.activity, False, False, 0)
        self.page('Dashboard', page)

    def make_assistant(self):
        page = box()
        controls = box(False)
        self.route = Gtk.ComboBoxText()
        for key, name in [('auto', 'Automatic'), ('local', 'Local'), ('advanced_local', 'Advanced Local'), ('cloud', 'Cloud')]:
            self.route.append(key, name)
        self.route.set_active_id('auto')
        controls.pack_start(self.route, False, False, 0)
        self.private = Gtk.CheckButton(label='Sensitive: keep local')
        controls.pack_start(self.private, False, False, 0)
        self.engine = Gtk.Label(label='LOCAL FIRST', xalign=1)
        controls.pack_end(self.engine, True, True, 0)
        page.pack_start(controls, False, False, 0)
        self.view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(18)
        self.view.set_right_margin(18)
        self.view.set_top_margin(16)
        self.buffer = self.view.get_buffer()
        self.buffer.create_tag('user', foreground='#72e5ff', weight=700)
        self.buffer.create_tag('muted', foreground='#a1b7cc')
        page.pack_start(scroll(self.view), True, True, 0)
        self.prompt = Gtk.Entry(placeholder_text='Ask JARVIS or type “show RAM usage”…')
        self.prompt.connect('activate', self.send)
        page.pack_start(self.prompt, False, False, 0)
        row = box(False)
        self.send_button = button('Send', self.send)
        self.stop_button = button('Stop', self.stop)
        self.stop_button.set_sensitive(False)
        self.regen_button = button('Regenerate', self.regenerate)
        row.pack_start(self.send_button, False, False, 0)
        row.pack_start(self.stop_button, False, False, 0)
        row.pack_start(self.regen_button, False, False, 0)
        row.pack_start(button('New conversation', self.new_conversation), False, False, 0)
        self.mic_button = button('Record 8 seconds', self.record)
        row.pack_end(self.mic_button, False, False, 0)
        row.pack_end(button('Read reply', self.read_reply), False, False, 0)
        page.pack_start(row, False, False, 0)
        self.page('Assistant', page)

    def append(self, text, tag=None):
        if self.buffer.get_char_count() + len(text) > 180000:
            self.buffer.delete(self.buffer.get_start_iter(), self.buffer.get_iter_at_offset(80000))
        end = self.buffer.get_end_iter()
        if tag:
            self.buffer.insert_with_tags_by_name(end, text, tag)
        else:
            self.buffer.insert(end, text)
        self.view.scroll_to_iter(self.buffer.get_end_iter(), 0, False, 0, 1)

    def send(self, *_args, consent=None, prompt=None, regenerate=False):
        if self.running:
            return
        text = prompt if prompt is not None else self.prompt.get_text().strip()
        if not text:
            return
        self.notebook.set_current_page(1)
        self.last_prompt = text
        self.last_answer = ''
        self.prompt.set_text('')
        self.append('\nYOU\n' + text + '\n\nJARVIS\n', 'user')
        self.running = True
        self.send_button.set_sensitive(False)
        self.regen_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        request = {'method': 'chat', 'prompt': text, 'route': self.route.get_active_id(), 'sensitive': self.private.get_active(), 'conversation': self.conversation}
        request['regenerate'] = regenerate
        if consent is not None:
            request['cloud_consent'] = consent
        self.worker(request)

    def chat_finished(self, _event):
        self.running = False
        self.generation = None
        self.send_button.set_sensitive(True)
        self.regen_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        self.append('\n')

    def stop(self, *_):
        if self.generation:
            self.worker({'method': 'cancel', 'generation': self.generation}, lambda _e: None)
        elif self.running:
            self.notice.set_text('Waiting for generation ID…')

    def regenerate(self, *_):
        if self.last_prompt and not self.running:
            # Remove last persisted pair from context without erasing stored history.
            self.send(prompt=self.last_prompt, regenerate=True)

    def new_conversation(self, *_):
        if self.running:
            self.notice.set_text('Stop the current response first.')
            return
        self.conversation = None
        self.last_prompt = ''
        self.last_answer = ''
        self.buffer.set_text('')
        self.notebook.set_current_page(1)

    def handle_event(self, event):
        kind = event.get('type')
        if kind == 'generation':
            self.generation = event['id']
        elif kind == 'conversation':
            self.conversation = event['id']
        elif kind == 'route':
            self.engine.set_text(event['kind'].upper().replace('_', ' ') + ' • ' + event['model'])
        elif kind == 'done':
            self.notice.set_text('Stopped. Partial output not saved.' if event.get('cancelled') else 'Response complete.' + (' Saved locally.' if event.get('saved') else ''))
        elif kind in {'error', 'notice'}:
            self.notice.set_text(event['message'])
            self.append('\n' + event['message'] + '\n', 'muted')
        elif kind == 'confirmation':
            dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.OK_CANCEL, text='Confirm action')
            dialog.format_secondary_text(json.dumps(event['action'], ensure_ascii=False) + '\nThis approval expires in 60 seconds.')
            answer = dialog.run()
            dialog.destroy()
            if answer == Gtk.ResponseType.OK:
                self.worker({'method': 'confirm', 'nonce': event['nonce']})
        elif kind == 'cloud_consent':
            dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO, text='Use cloud intelligence?')
            dialog.format_secondary_text(event['message'])
            answer = dialog.run()
            dialog.destroy()
            # chat worker's completion callback must reset busy state before resend.
            GLib.idle_add(self.resend_consent, answer == Gtk.ResponseType.YES, self.last_prompt)
        elif kind == 'result':
            self.notice.set_text(str(event.get('value', 'Done'))[:300])

    def resend_consent(self, consent, text):
        if self.running:
            GLib.timeout_add(50, self.resend_consent, consent, text)
            return False
        self.send(prompt=text, consent=consent)
        return False

    def status(self):
        if self.closed:
            return False
        if not self.status_busy:
            self.status_busy = True
            self.worker({'method': 'status'}, self.status_result)
        return True

    def status_result(self, event):
        self.status_busy = False
        if event['type'] != 'result':
            self.connection.set_text('Core offline • apps available')
            self.node_state.clear()
            self.metrics['Local AI'].set_text('Unknown • Core offline')
            return
        self.connection.set_text('Core online • private connection')
        value = event['value']
        self.config = value['config']
        if not self.settings_loaded:
            self.load_settings()
            self.settings_loaded = True
        state = value['system']
        self.clock.set_text(state['time'].replace('T', '  '))
        self.metrics['CPU'].set_text(str(state['cpu_percent']) + '%' if state['cpu_percent'] is not None else 'Sampling…')
        ram = state['ram']
        self.metrics['RAM'].set_text(f"{ram['used_mb']:.0f} / {ram['total_mb']:.0f} MiB" if ram else 'Unavailable')
        disk = state['disk']
        self.metrics['Storage'].set_text(f"{disk['used_gb']} / {disk['total_gb']} GiB")
        battery = state['battery']
        self.metrics['Battery'].set_text(f"{battery['percent']}% • {battery['state']}" if battery else 'No battery detected')
        self.metrics['Network'].set_text(', '.join(state['network']) or 'No active link')
        self.metrics['Internet'].set_text(state['internet'])
        enabled = [p for p in self.config['profiles'] if p['enabled'] and p['kind'] != 'cloud']
        self.metrics['Local AI'].set_text('\n'.join(p['label'] + ': ' + self.node_state.get(p['id'], 'Not tested') + ' • ' + p['model'] for p in enabled) or 'Configure a Local AI Node')
        self.metrics['Cloud'].set_text('Enabled • ' + self.config['mode'].replace('_', ' ') if self.config['cloud_enabled'] else 'Disabled')
        # LAN-only health check every 60s when idle; no hidden cloud requests.
        now = time.monotonic()
        if enabled and not self.running and now - self.probe_at > 60:
            self.probe_at = now
            self.probe_nodes(enabled)

    def probe_nodes(self, profiles=None):
        profiles = profiles if profiles is not None else [p for p in self.config.get('profiles', []) if p['enabled'] and p['kind'] != 'cloud']
        for p in profiles:
            def done(event, ident=p['id']):
                self.node_state[ident] = 'Online' if event['type'] == 'result' else 'Offline / authentication failed'
                self.notice.set_text(ident + ': ' + self.node_state[ident])
            self.worker({'method': 'probe', 'id': p['id']}, done)

    def make_apps(self):
        page = box()
        row = box(False)
        self.app_search = Gtk.SearchEntry(placeholder_text='Search installed applications')
        self.app_search.connect('search-changed', self.refresh_apps)
        row.pack_start(self.app_search, True, True, 0)
        self.category = Gtk.ComboBoxText()
        for name in ['All', 'Favorites', 'Recent', 'Development', 'Network', 'Office', 'Utility', 'System', 'AudioVideo', 'Graphics', 'Game']:
            self.category.append_text(name)
        self.category.set_active(0)
        self.category.connect('changed', self.refresh_apps)
        row.pack_end(self.category, False, False, 0)
        page.pack_start(row, False, False, 0)
        self.app_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.app_list.connect('row-activated', lambda _, row: self.launch_app(row.app))
        page.pack_start(scroll(self.app_list), True, True, 0)
        page.pack_start(Gtk.Label(label='Arrow keys select • Enter opens • ☆ marks a favorite', xalign=0), False, False, 0)
        self.page('Applications', page)
        self.refresh_apps()

    def refresh_apps(self, *_):
        for item in self.app_list.get_children():
            self.app_list.remove(item)
        query = self.app_search.get_text().lower()
        category = self.category.get_active_text()
        apps = [a for a in Gio.AppInfo.get_all() if a.should_show() and query in (a.get_display_name() + ' ' + (a.get_description() or '')).lower()]
        for app in sorted(apps, key=lambda a: (a.get_id() not in self.favorites, a.get_display_name().lower())):
            ident = app.get_id()
            cats = (app.get_categories() or '').split(';') if isinstance(app, Gio.DesktopAppInfo) else []
            if category == 'Favorites' and ident not in self.favorites or category == 'Recent' and ident not in self.recents:
                continue
            if category not in {'All', 'Favorites', 'Recent'} and category not in cats:
                continue
            row = Gtk.ListBoxRow()
            row.app = app
            content = box(False)
            content.set_border_width(6)
            content.pack_start(Gtk.Label(label=app.get_display_name(), xalign=0), True, True, 0)
            content.pack_end(button('★' if ident in self.favorites else '☆', lambda _, i=ident: self.favorite(i)), False, False, 0)
            content.pack_end(button('Open', lambda _, a=app: self.launch_app(a)), False, False, 0)
            row.add(content)
            self.app_list.add(row)
        self.app_list.show_all()

    def save_launcher(self):
        atomic_write(self.launch_file, json.dumps({'favorites': self.favorites, 'recents': self.recents}))

    def favorite(self, ident):
        if ident in self.favorites:
            self.favorites.remove(ident)
        else:
            self.favorites.append(ident)
        self.favorites = self.favorites[:30]
        self.save_launcher()
        self.refresh_apps()

    def launch_app(self, app):
        try:
            app.launch([], Gdk.Display.get_default().get_app_launch_context())
            ident = app.get_id()
            self.recents = ([ident] + [i for i in self.recents if i != ident])[:12]
            self.save_launcher()
            self.activity.set_text('Launched ' + app.get_display_name())
            self.notice.set_text('Launched ' + app.get_display_name())
        except Exception:
            self.notice.set_text('Application could not be launched.')

    def launch_named(self, ident):
        app = Gio.DesktopAppInfo.new(ident)
        if app:
            self.launch_app(app)
        else:
            self.notice.set_text('Application not installed: ' + ident)

    def make_history(self):
        page = box()
        page.pack_start(button('Refresh conversation history', self.refresh_history), False, False, 0)
        self.history_list = Gtk.ListBox()
        self.history_list.connect('row-activated', self.load_history)
        page.pack_start(scroll(self.history_list), True, True, 0)
        self.page('History', page)

    def refresh_history(self, *_):
        def done(event):
            if event['type'] != 'result':
                self.handle_event(event)
                return
            for row in self.history_list.get_children():
                self.history_list.remove(row)
            for item in event['value']:
                row = Gtk.ListBoxRow()
                row.ident = item['id']
                content = box(False)
                content.pack_start(Gtk.Label(label=item['title'], xalign=0), True, True, 0)
                content.pack_end(button('Delete', lambda _, i=item['id']: self.worker({'method': 'delete_conversation', 'id': i})), False, False, 0)
                row.add(content)
                self.history_list.add(row)
            self.history_list.show_all()
        self.worker({'method': 'conversations'}, done)

    def load_history(self, _, row):
        if self.running:
            return
        ident = row.ident
        self.conversation = ident
        self.buffer.set_text('')
        self.last_prompt = ''
        self.last_answer = ''
        current = {'role': '', 'content': ''}
        self.notebook.set_current_page(1)
        def done(event):
            if event['type'] == 'history_start':
                current.update(role=event['role'], content='')
                self.append(event['role'].upper() + '\n')
            elif event['type'] == 'history_chunk':
                current['content'] += event['text']
                self.append(event['text'])
            elif event['type'] == 'history_end':
                self.append('\n\n')
                if current['role'] == 'user':
                    self.last_prompt = current['content']
                elif current['role'] == 'assistant':
                    self.last_answer = current['content']
            elif event['type'] == 'error':
                self.handle_event(event)
        self.worker({'method': 'history_stream', 'conversation': ident}, done)

    def make_memory(self):
        page = box()
        self.fact_search = Gtk.Entry(placeholder_text='Search saved local facts')
        self.fact_search.connect('activate', self.refresh_facts)
        row = box(False)
        row.pack_start(self.fact_search, True, True, 0)
        row.pack_end(button('Search', self.refresh_facts), False, False, 0)
        page.pack_start(row, False, False, 0)
        self.fact_list = Gtk.ListBox()
        page.pack_start(scroll(self.fact_list), True, True, 0)
        self.fact_entry = Gtk.Entry(placeholder_text='Save an important fact or preference explicitly')
        page.pack_start(self.fact_entry, False, False, 0)
        row = box(False)
        row.pack_start(button('Remember', self.remember), False, False, 0)
        row.pack_end(button('Clear all facts and history…', lambda *_: self.worker({'method': 'clear_memory'})), False, False, 0)
        page.pack_start(row, False, False, 0)
        self.page('Memory', page)

    def remember(self, *_):
        text = self.fact_entry.get_text().strip()
        if text:
            def done(event):
                if event['type'] == 'result':
                    self.notice.set_text('Fact saved in local memory.')
                    self.fact_entry.set_text('')
                    self.refresh_facts()
                else:
                    self.handle_event(event)
            self.worker({'method': 'remember', 'content': text}, done)

    def refresh_facts(self, *_):
        def done(event):
            if event['type'] != 'result':
                self.handle_event(event)
                return
            for row in self.fact_list.get_children():
                self.fact_list.remove(row)
            for item in event['value']:
                row = box(False)
                label = Gtk.Label(label=item['content'], xalign=0)
                label.set_line_wrap(True)
                row.pack_start(label, True, True, 0)
                row.pack_end(button('Delete…', lambda _, i=item['id']: self.worker({'method': 'delete_fact', 'id': i})), False, False, 0)
                self.fact_list.add(row)
            self.fact_list.show_all()
        self.worker({'method': 'facts', 'query': self.fact_search.get_text()}, done)

    def make_settings(self):
        page = box()
        page.pack_start(Gtk.Label(label='AI & privacy • changes remain on this computer', xalign=0), False, False, 0)
        self.mode = Gtk.ComboBoxText()
        for mode in ['local_only', 'local_first', 'ask_before_cloud', 'cloud_preferred']:
            self.mode.append(mode, mode.replace('_', ' ').title())
        self.mode.set_active_id('local_first')
        page.pack_start(self.mode, False, False, 0)
        self.cloud_enabled = Gtk.CheckButton(label='Enable configured cloud providers')
        self.memory_enabled = Gtk.CheckButton(label='Retrieve user-saved local memory')
        self.history_enabled = Gtk.CheckButton(label='Save complete conversations locally')
        self.memory_enabled.set_active(True)
        self.history_enabled.set_active(True)
        for widget in [self.cloud_enabled, self.memory_enabled, self.history_enabled]:
            page.pack_start(widget, False, False, 0)
        self.retention = Gtk.SpinButton.new_with_range(1, 3650, 1)
        self.retention.set_value(30)
        row = box(False)
        row.pack_start(Gtk.Label(label='Retention (days)'), False, False, 0)
        row.pack_start(self.retention, False, False, 0)
        row.pack_start(button('Load current', self.load_settings), False, False, 0)
        row.pack_start(button('Save preferences', self.save_settings), False, False, 0)
        page.pack_start(row, False, False, 0)
        row = box(False)
        for ident, title in [('tablet', 'Primary Local Node'), ('advanced', 'Advanced Local'), ('groq', 'Groq'), ('gemini', 'Gemini'), ('openrouter', 'OpenRouter')]:
            row.pack_start(button(title, lambda _, i=ident: self.profile_dialog(i)), False, False, 0)
        page.pack_start(row, False, False, 0)
        page.pack_start(button('Test enabled Local AI Nodes', lambda *_: self.probe_nodes()), False, False, 0)
        self.voice_model = Gtk.Entry(placeholder_text='Optional offline Vosk model directory')
        page.pack_start(self.voice_model, False, False, 0)
        page.pack_start(button('Save voice model path', lambda *_: self.worker({'method': 'voice_settings', 'model': self.voice_model.get_text()})), False, False, 0)
        tools = box(False)
        for title, ident in [('Wi-Fi', 'nm-connection-editor.desktop'), ('Audio', 'pavucontrol.desktop'), ('Bluetooth', 'blueman-manager.desktop'), ('Display', 'arandr.desktop'), ('Power', 'xfce4-power-manager-settings.desktop'), ('Appearance', 'lxappearance.desktop')]:
            tools.pack_start(button(title, lambda _, i=ident: self.launch_named(i)), False, False, 0)
        page.pack_start(tools, False, False, 0)
        page.pack_start(Gtk.Label(label='Updates: use the Terminal with sudo apt update and sudo apt upgrade.\nNo cloud keys or models are bundled. Browser and system tools start only when opened.\nNo always-on microphone, automatic device trust, or laptop LLM inference.', xalign=0), False, False, 0)
        self.page('Settings', page)

    def load_settings(self, *_):
        if not self.config:
            return
        self.mode.set_active_id(self.config['mode'])
        for name in ['cloud_enabled', 'memory_enabled', 'history_enabled']:
            getattr(self, name).set_active(self.config[name])
        self.retention.set_value(self.config['retention_days'])
        self.voice_model.set_text(self.config.get('voice', {}).get('stt_model', ''))

    def save_settings(self, *_):
        changes = {'mode': self.mode.get_active_id(), 'retention_days': self.retention.get_value_as_int()}
        for name in ['cloud_enabled', 'memory_enabled', 'history_enabled']:
            changes[name] = getattr(self, name).get_active()
        self.worker({'method': 'preferences', 'changes': changes})

    def profile_dialog(self, ident):
        profile = next((p for p in self.config.get('profiles', []) if p['id'] == ident), None)
        if not profile:
            self.notice.set_text('Wait for Core connection before editing nodes.')
            return
        dialog = Gtk.Dialog(title=profile['label'], transient_for=self, modal=True)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Save', Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_border_width(16)
        content.set_spacing(8)
        enabled = Gtk.CheckButton(label='Enable this provider')
        enabled.set_active(profile['enabled'])
        content.pack_start(enabled, False, False, 0)
        entries = {}
        for key, label in [('url', 'OpenAI-compatible base URL'), ('model', 'Exact model ID from /v1/models')]:
            content.pack_start(Gtk.Label(label=label, xalign=0), False, False, 0)
            entry = Gtk.Entry(text=profile[key], width_chars=50)
            content.pack_start(entry, False, False, 0)
            entries[key] = entry
        key_entry = Gtk.Entry(placeholder_text='New API key (blank keeps existing)', visibility=False)
        content.pack_start(key_entry, False, False, 0)
        insecure = Gtk.CheckButton(label='Allow unencrypted LAN HTTP (trusted network only)')
        insecure.set_active(bool(profile.get('allow_insecure_lan')))
        content.pack_start(insecure, False, False, 0)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            changes = {key: entry.get_text().strip() for key, entry in entries.items()}
            changes.update(enabled=enabled.get_active(), allow_insecure_lan=insecure.get_active())
            self.worker({'method': 'profile', 'id': ident, 'changes': changes, 'key': key_entry.get_text().strip()})
        key_entry.set_text('')
        dialog.destroy()

    def record(self, *_):
        if self.recording:
            return
        self.recording = True
        self.mic_button.set_sensitive(False)
        self.mic_button.set_label('MIC ON • 8 seconds')
        def work():
            try:
                result = transcribe(self.config.get('voice', {}).get('stt_model', ''))
                self.enqueue(self.record_done, {'text': result})
            except Exception as error:
                self.enqueue(self.record_done, {'error': str(error)})
        threading.Thread(target=work, daemon=True).start()

    def make_search(self):
        page = box()
        self.web_query = Gtk.Entry(placeholder_text='Web search query • sent only when you click Search')
        page.pack_start(self.web_query, False, False, 0)
        row = box(False)
        row.pack_start(button('Search in browser', self.browser_search), False, False, 0)
        row.pack_start(button('Retrieve sources (configured SearXNG)', self.retrieve), False, False, 0)
        page.pack_start(row, False, False, 0)
        self.sources = Gtk.ListBox()
        page.pack_start(scroll(self.sources), True, True, 0)
        page.pack_start(Gtk.Label(label='Retrieval is separate from model knowledge. Review sources before using them.\nConfigure an owned LAN SearXNG instance in config.toml to enable JSON retrieval.', xalign=0), False, False, 0)
        self.page('Search', page)

    def browser_search(self, *_):
        query = self.web_query.get_text().strip()
        if query:
            Gio.AppInfo.launch_default_for_uri('https://duckduckgo.com/?' + urllib.parse.urlencode({'q': query}), None)

    def retrieve(self, *_):
        query = self.web_query.get_text().strip()
        if not query:
            return
        def done(event):
            if event['type'] != 'result':
                self.handle_event(event)
                return
            for row in self.sources.get_children():
                self.sources.remove(row)
            for source in event['value']:
                row = box()
                row.pack_start(Gtk.LinkButton.new_with_label(source['url'], source['title']), False, False, 0)
                label = Gtk.Label(label=source['snippet'], xalign=0)
                label.set_line_wrap(True)
                row.pack_start(label, False, False, 0)
                self.sources.add(row)
            self.sources.show_all()
        self.worker({'method': 'search', 'query': query}, done)

    def record_done(self, result):
        self.recording = False
        self.mic_button.set_sensitive(True)
        self.mic_button.set_label('Record 8 seconds')
        if 'error' in result:
            self.notice.set_text(result['error'])
        else:
            self.prompt.set_text(result['text'])
            self.notice.set_text('Microphone off. Review transcription before sending.')

    def read_reply(self, *_):
        if not self.last_answer:
            return
        def work():
            try:
                speak(self.last_answer)
            except Exception as error:
                self.enqueue(self.handle_event, {'type': 'notice', 'message': str(error)})
        threading.Thread(target=work, daemon=True).start()

    def close(self, *_):
        self.stop()
        self.closed = True
        if Gtk.main_level():
            Gtk.main_quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-root-for-tests', action='store_true')
    args = parser.parse_args()
    if os.getuid() == 0 and not args.allow_root_for_tests:
        parser.error('The desktop must run as a non-root user')
    os.umask(0o077)
    Desktop()
    Gtk.main()


if __name__ == '__main__':
    main()
