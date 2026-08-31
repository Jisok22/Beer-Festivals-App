from datetime import date, timedelta
import calendar
import webbrowser
import urllib.parse

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.checkbox import CheckBox
from kivy.factory import Factory

import database
from database import FirebaseError

DAYS = [str(d) for d in range(1, 32)]
MONTHS = list(calendar.month_name)[1:]
CURRENT_YEAR = date.today().year
YEARS = [str(y) for y in range(CURRENT_YEAR, CURRENT_YEAR + 5)]

TIMES = []
for hour in range(8, 23):
    for minute in (0, 30):
        TIMES.append(f"{hour:02d}:{minute:02d}")


class RootWidget(FloatLayout):
    pass


def add_form_row(form, label_text, field, row_height=None):
    row_height = row_height if row_height is not None else dp(44)
    row = BoxLayout(spacing=dp(0), size_hint_y=None, height=row_height)
    label = Factory.StyledLabel(text=label_text, font_size="13sp", size_hint_x=0.33)
    label.valign = "middle"
    label.bind(size=label.setter("text_size"))
    row.add_widget(label)
    field.size_hint = (0.67, None)
    field.height = row_height
    row.add_widget(field)
    form.add_widget(row)


class PullToRefreshScrollView(ScrollView):
    def __init__(self, refresh_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.refresh_callback = refresh_callback
        self._pull_triggered = False

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud["pull_start_y"] = touch.y
            # Check if scroll is near top (scroll_y ranges from 0.0 bottom to 1.0 top)
            touch.ud["pull_started_at_top"] = self.scroll_y >= 0.98
            touch.ud["pull_active"] = True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.ud.get("pull_active"):
            start_y = touch.ud.get("pull_start_y", touch.y)
            started_at_top = touch.ud.get("pull_started_at_top", False)
            
            # Kivy's y-axis increases upward, so a downward drag decreases touch.y
            if started_at_top and (start_y - touch.y) >= dp(60):
                self._pull_triggered = True

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        should_refresh = self._pull_triggered
        self._pull_triggered = False
        
        if touch.ud.get("pull_active"):
            touch.ud["pull_active"] = False

        handled = super().on_touch_up(touch)

        if should_refresh and self.refresh_callback:
            Clock.schedule_once(lambda dt: self.refresh_callback(), 0)

        return handled


class FestivalApp(App):
    def build(self):
        database.init_db()

        self.editing_festival_id = None
        self.editing_festival = None
        self.editing_resource_id = None
        self.active_tab = "current"
        self.viewing_festival = None

        root = RootWidget()

        list_container = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        heading = Factory.StyledLabel(
            text="Beer Festival Organiser",
            font_size="18sp",
            bold=True,
            halign="center",
            size_hint_y=None,
            height=dp(44),
        )
        heading.bind(size=heading.setter("text_size"))
        list_container.add_widget(heading)

        self.list_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(8))
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))

        scroll = PullToRefreshScrollView(refresh_callback=self.refresh_list)
        scroll.add_widget(self.list_layout)
        list_container.add_widget(scroll)

        self.nav_bar = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8)
        )
        list_container.add_widget(self.nav_bar)

        root.add_widget(list_container)

        add_button = Factory.FloatingAddButton(
            text="+",
            size_hint=(None, None),
            size=(dp(38.4), dp(38.4)),
            pos_hint={"right": 0.95, "top": 0.98},
        )
        add_button.bind(on_press=self.handle_add_button)
        root.add_widget(add_button)

        self.refresh_nav_bar()
        Clock.schedule_once(lambda dt: self.refresh_list())

        return root

    def handle_add_button(self, instance):
        if self.active_tab == "resources":
            self.open_add_resource_popup()
        else:
            self.open_add_popup(instance)

    def switch_tab(self, tab_name):
        tab_changed = tab_name != self.active_tab
        self.active_tab = tab_name
        self.viewing_festival = None
        if tab_changed:
            self.refresh_nav_bar()
        self.refresh_list()

    def show_festival_detail(self, festival):
        self.viewing_festival = festival
        self.refresh_list()

    def close_festival_detail(self):
        self.viewing_festival = None
        self.refresh_list()

    def refresh_nav_bar(self):
        self.nav_bar.clear_widgets()

        tabs = [
            ("current", "Upcoming"),
            ("previous", "Previous"),
            ("resources", "Resources"),
        ]
        for tab_name, label in tabs:
            is_active = tab_name == self.active_tab
            nav_button = (Factory.RoundedButton if is_active else Factory.CancelButton)(
                text=label, font_size="12sp"
            )
            nav_button.bind(on_press=lambda instance, name=tab_name: self.switch_tab(name))
            self.nav_bar.add_widget(nav_button)

    def show_error_popup(self, message):
        content = Factory.StyledLabel(
            text=message,
            halign="center",
            valign="middle",
        )
        content.bind(size=content.setter("text_size"))
        error_popup = Popup(
            title="Something went wrong",
            content=content,
            size_hint=(0.8, 0.4),
        )
        error_popup.open()

    def open_add_popup(self, instance, festival=None):
        self.editing_festival_id = festival["id"] if festival else None
        self.editing_festival = festival

        popup_layout = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(5))

        form = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(10),
            size_hint_y=None,
        )
        form.bind(minimum_height=form.setter("height"))

        self.name_input = Factory.StyledTextInput(multiline=True)
        add_form_row(form, "Name:", self.name_input, row_height=dp(60))

        self.location_input = Factory.StyledTextInput(multiline=True)
        add_form_row(form, "Location /\nAddress:", self.location_input, row_height=dp(70))

        self.website_input = Factory.StyledTextInput(multiline=False)
        add_form_row(form, "Website:", self.website_input)

        start_row = BoxLayout(spacing=dp(5))
        self.start_day = Spinner(text=DAYS[0], values=DAYS, font_size="11sp")
        self.start_month = Spinner(text=MONTHS[0], values=MONTHS, font_size="11sp")
        self.start_year = Spinner(text=YEARS[0], values=YEARS, font_size="11sp")
        start_row.add_widget(self.start_day)
        start_row.add_widget(self.start_month)
        start_row.add_widget(self.start_year)
        add_form_row(form, "Start date:", start_row)

        times_row = BoxLayout(spacing=dp(5))
        self.open_time_spinner = Spinner(text=TIMES[0], values=TIMES, font_size="11sp")
        self.close_time_spinner = Spinner(text=TIMES[-1], values=TIMES, font_size="11sp")
        times_row.add_widget(self.open_time_spinner)
        times_row.add_widget(self.close_time_spinner)
        add_form_row(form, "Open / Close:", times_row)

        self.one_day_checkbox = CheckBox(size_hint=(None, None), size=(dp(30), dp(30)))
        self.one_day_checkbox.bind(active=self.toggle_one_day)
        checkbox_row = AnchorLayout(anchor_x="left", anchor_y="center")
        checkbox_row.add_widget(self.one_day_checkbox)
        add_form_row(form, "One day only:", checkbox_row, row_height=dp(40))

        self.varies_by_day_checkbox = CheckBox(size_hint=(None, None), size=(dp(30), dp(30)))
        self.varies_by_day_checkbox.bind(active=self.rebuild_day_times_rows)
        varies_row = AnchorLayout(anchor_x="left", anchor_y="center")
        varies_row.add_widget(self.varies_by_day_checkbox)
        add_form_row(form, "Different times\nafter day 1:", varies_row, row_height=dp(40))

        end_row = BoxLayout(spacing=dp(5))
        self.end_day = Spinner(text=DAYS[0], values=DAYS, font_size="11sp")
        self.end_month = Spinner(text=MONTHS[0], values=MONTHS, font_size="11sp")
        self.end_year = Spinner(text=YEARS[0], values=YEARS, font_size="11sp")
        end_row.add_widget(self.end_day)
        end_row.add_widget(self.end_month)
        end_row.add_widget(self.end_year)
        add_form_row(form, "End date:", end_row)

        self.day_times_container = BoxLayout(
            orientation="vertical", spacing=dp(4), size_hint_y=None
        )
        self.day_times_container.bind(
            minimum_height=self.day_times_container.setter("height")
        )
        form.add_widget(self.day_times_container)

        self.start_day.bind(text=self.update_end_date)
        self.start_month.bind(text=self.update_end_date)
        self.start_year.bind(text=self.update_end_date)

        for control, event_name in (
            (self.start_day, "text"),
            (self.start_month, "text"),
            (self.start_year, "text"),
            (self.end_day, "text"),
            (self.end_month, "text"),
            (self.end_year, "text"),
            (self.one_day_checkbox, "active"),
        ):
            control.bind(**{event_name: self.rebuild_day_times_rows})

        form_scroll = ScrollView(size_hint=(1, 1))
        form_scroll.add_widget(form)

        if festival:
            # Pre-fill every field with the existing festival's details.
            self.name_input.text = festival["name"]
            self.location_input.text = festival["location"]
            self.website_input.text = festival.get("website", "")

            self.start_day.text = str(festival["start_date"].day)
            self.start_month.text = MONTHS[festival["start_date"].month - 1]
            self.start_year.text = str(festival["start_date"].year)

            self.end_day.text = str(festival["end_date"].day)
            self.end_month.text = MONTHS[festival["end_date"].month - 1]
            self.end_year.text = str(festival["end_date"].year)

            if festival["opening_time"]:
                self.open_time_spinner.text = festival["opening_time"]
            if festival["closing_time"]:
                self.close_time_spinner.text = festival["closing_time"]

            # Setting .active triggers toggle_one_day / rebuild_day_times_rows, which
            # correctly disable the end-date spinners and build the per-day rows.
            self.one_day_checkbox.active = (festival["start_date"] == festival["end_date"])
            self.varies_by_day_checkbox.active = festival["varies_by_day"]
        else:
            self.update_end_date()

        popup_layout.add_widget(form_scroll)

        button_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        if festival:
            delete_button = Factory.CancelButton(text="Delete", font_size="14sp")
            delete_button.bind(
                on_press=lambda instance: self.show_delete_confirmation(
                    "Delete this festival? This can't be undone.",
                    lambda confirm_popup: self.delete_festival(festival["id"], confirm_popup),
                )
            )
            button_row.add_widget(delete_button)

        cancel_button = Factory.CancelButton(text="Cancel", font_size="14sp")
        button_row.add_widget(cancel_button)

        save_button = Factory.RoundedButton(text="Save", font_size="14sp")
        button_row.add_widget(save_button)

        popup_layout.add_widget(button_row)

        self.popup = Popup(
            title="Edit Festival" if festival else "Add Festival",
            content=popup_layout,
            size_hint=(0.9, 0.8),
        )
        save_button.bind(on_press=self.save_festival)
        cancel_button.bind(on_press=self.popup.dismiss)

        self.popup.open()

    def show_delete_confirmation(self, message_text, delete_action):
        confirm_layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

        message = Factory.StyledLabel(
            text=message_text,
            halign="center",
            valign="middle",
        )
        message.bind(size=message.setter("text_size"))
        confirm_layout.add_widget(message)

        button_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        confirm_popup = Popup(
            title="Confirm deletion",
            content=confirm_layout,
            size_hint=(0.8, 0.4),
        )

        cancel_button = Factory.CancelButton(text="Cancel", font_size="14sp")
        cancel_button.bind(on_press=confirm_popup.dismiss)
        button_row.add_widget(cancel_button)

        confirm_button = Factory.RoundedButton(text="Confirm", font_size="14sp")
        confirm_button.bind(on_press=lambda instance: delete_action(confirm_popup))
        button_row.add_widget(confirm_button)

        confirm_layout.add_widget(button_row)

        confirm_popup.open()

    def delete_festival(self, festival_id, confirm_popup):
        try:
            database.delete_festival(festival_id)
        except FirebaseError:
            confirm_popup.dismiss()
            self.show_error_popup(
                "Couldn't delete the festival. Check your internet connection and try again."
            )
            return

        confirm_popup.dismiss()
        self.popup.dismiss()
        self.refresh_list()

    def toggle_one_day(self, checkbox, is_active):
        self.end_day.disabled = is_active
        self.end_month.disabled = is_active
        self.end_year.disabled = is_active

    def get_selected_date_range(self):
        try:
            start_date = date(
                int(self.start_year.text),
                MONTHS.index(self.start_month.text) + 1,
                int(self.start_day.text),
            )
        except ValueError:
            return None, None

        if self.one_day_checkbox.active:
            end_date = start_date
        else:
            try:
                end_date = date(
                    int(self.end_year.text),
                    MONTHS.index(self.end_month.text) + 1,
                    int(self.end_day.text),
                )
            except ValueError:
                return None, None

        if end_date < start_date:
            return None, None

        return start_date, end_date

    def rebuild_day_times_rows(self, *args):
        self.day_times_container.clear_widgets()
        self.day_time_spinners = {}

        if not self.varies_by_day_checkbox.active:
            return

        start_date, end_date = self.get_selected_date_range()
        if start_date is None or end_date <= start_date:
            return

        saved_day_times = {}
        if self.editing_festival:
            saved_day_times = self.editing_festival.get("day_times", {})

        current_date = start_date + timedelta(days=1)
        while current_date <= end_date:
            date_iso = current_date.isoformat()
            saved = saved_day_times.get(date_iso, {})

            day_times_row = BoxLayout(spacing=dp(5))
            open_spinner = Spinner(
                text=saved.get("open", TIMES[0]), values=TIMES, font_size="11sp"
            )
            close_spinner = Spinner(
                text=saved.get("close", TIMES[-1]), values=TIMES, font_size="11sp"
            )
            day_times_row.add_widget(open_spinner)
            day_times_row.add_widget(close_spinner)

            add_form_row(
                self.day_times_container,
                f"{current_date.strftime('%a %d %b')}:",
                day_times_row,
                row_height=dp(36),
            )

            self.day_time_spinners[date_iso] = (open_spinner, close_spinner)

            current_date += timedelta(days=1)

    def update_end_date(self, *_):
        try:
            start_date = date(
                int(self.start_year.text),
                MONTHS.index(self.start_month.text) + 1,
                int(self.start_day.text),
            )
        except ValueError:
            return

        end_date = start_date + timedelta(days=1)
        if str(end_date.year) not in YEARS:
            return

        self.end_day.text = str(end_date.day)
        self.end_month.text = MONTHS[end_date.month - 1]
        self.end_year.text = str(end_date.year)

    def save_festival(self, instance):
        name = self.name_input.text.strip()
        location = self.location_input.text.strip()
        website = self.website_input.text.strip()

        if not name:
            return

        start_date, end_date = self.get_selected_date_range()
        if start_date is None:
            return

        opening_time = self.open_time_spinner.text
        closing_time = self.close_time_spinner.text
        varies_by_day = self.varies_by_day_checkbox.active

        day_times = {}
        if varies_by_day:
            for date_iso, (open_spinner, close_spinner) in self.day_time_spinners.items():
                day_times[date_iso] = {"open": open_spinner.text, "close": close_spinner.text}

        try:
            if self.editing_festival_id:
                database.update_festival(
                    self.editing_festival_id,
                    name,
                    location,
                    start_date,
                    end_date,
                    opening_time,
                    closing_time,
                    varies_by_day,
                    day_times,
                    website,
                )
            else:
                database.add_festival(
                    name,
                    location,
                    start_date,
                    end_date,
                    opening_time,
                    closing_time,
                    varies_by_day,
                    day_times,
                    website,
                )
        except FirebaseError:
            self.show_error_popup(
                "Couldn't save the festival. Check your internet connection and try again."
            )
            return

        self.refresh_list()
        self.popup.dismiss()

    def open_add_resource_popup(self, instance=None, resource=None):
        self.editing_resource_id = resource["id"] if resource else None

        popup_layout = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(5))

        form = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(10),
            size_hint_y=None,
        )
        form.bind(minimum_height=form.setter("height"))

        self.resource_name_input = Factory.StyledTextInput(multiline=False)
        add_form_row(form, "Name:", self.resource_name_input)

        self.resource_url_input = Factory.StyledTextInput(multiline=False)
        add_form_row(form, "Website:", self.resource_url_input)

        if resource:
            self.resource_name_input.text = resource["name"]
            self.resource_url_input.text = resource["url"]

        popup_layout.add_widget(form)

        button_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        if resource:
            delete_button = Factory.CancelButton(text="Delete", font_size="14sp")
            delete_button.bind(
                on_press=lambda instance: self.show_delete_confirmation(
                    "Delete this resource? This can't be undone.",
                    lambda confirm_popup: self.delete_resource(resource["id"], confirm_popup),
                )
            )
            button_row.add_widget(delete_button)

        cancel_button = Factory.CancelButton(text="Cancel", font_size="14sp")
        button_row.add_widget(cancel_button)

        save_button = Factory.RoundedButton(text="Save", font_size="14sp")
        button_row.add_widget(save_button)

        popup_layout.add_widget(button_row)

        self.popup = Popup(
            title="Edit Resource" if resource else "Add Resource",
            content=popup_layout,
            size_hint=(0.9, 0.5),
        )
        save_button.bind(on_press=self.save_resource)
        cancel_button.bind(on_press=self.popup.dismiss)

        self.popup.open()

    def save_resource(self, instance):
        name = self.resource_name_input.text.strip()
        url = self.resource_url_input.text.strip()

        if not name or not url:
            return

        try:
            if self.editing_resource_id:
                database.update_resource(self.editing_resource_id, name, url)
            else:
                database.add_resource(name, url)
        except FirebaseError:
            self.show_error_popup(
                "Couldn't save the resource. Check your internet connection and try again."
            )
            return

        self.refresh_list()
        self.popup.dismiss()

    def delete_resource(self, resource_id, confirm_popup):
        try:
            database.delete_resource(resource_id)
        except FirebaseError:
            confirm_popup.dismiss()
            self.show_error_popup(
                "Couldn't delete the resource. Check your internet connection and try again."
            )
            return

        confirm_popup.dismiss()
        self.popup.dismiss()
        self.refresh_list()

    def open_in_maps(self, location_text):
        query = urllib.parse.quote(location_text)
        url = f"https://www.google.com/maps/search/?api=1&query={query}"
        webbrowser.open(url)

    def open_website(self, url):
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            url = f"https://{url}"
        webbrowser.open(url)

    def refresh_list(self):
        self.list_layout.clear_widgets()

        if self.viewing_festival:
            self.list_layout.add_widget(self.build_festival_detail(self.viewing_festival))
            return

        if self.active_tab == "resources":
            try:
                resources = database.get_all_resources()
            except FirebaseError:
                self.show_error_popup(
                    "Couldn't load resources. Check your internet connection and try again."
                )
                return

            for resource in resources:
                self.list_layout.add_widget(self.build_resource_card(resource))
            return

        try:
            festivals = database.get_all_festivals()
        except FirebaseError:
            self.show_error_popup(
                "Couldn't load the festival list. Check your internet connection and try again."
            )
            return

        today = date.today()
        if self.active_tab == "previous":
            festivals = [f for f in festivals if f["end_date"] < today]
            festivals.sort(key=lambda f: f["start_date"], reverse=True)
        else:
            festivals = [f for f in festivals if f["end_date"] >= today]

        for festival in festivals:
            self.list_layout.add_widget(self.build_festival_card(festival))

    def build_resource_card(self, resource):
        card = Factory.FestivalCard(orientation="horizontal", height=dp(56))

        name_label = Factory.StyledLabel(
            text=f"{resource['name']} [size=11sp][color=#D2691E] edit[/color][/size]",
            font_size="14sp",
            bold=True,
            halign="left",
            valign="middle",
            markup=True,
        )
        name_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        name_label.bind(
            on_touch_down=lambda label, touch, res=resource: (
                self.open_add_resource_popup(None, res)
                if label.collide_point(*touch.pos)
                else False
            )
        )
        card.add_widget(name_label)

        link_icon = Factory.LinkIcon(
            text="Link",
            size_hint=(None, None),
            size=(dp(40), dp(28)),
            pos_hint={"center_y": 0.5},
        )
        link_icon.bind(on_press=lambda instance, url=resource["url"]: self.open_website(url))
        card.add_widget(link_icon)

        return card

    def build_festival_card(self, festival):
        card = Factory.FestivalCard(orientation="vertical", height=dp(88), spacing=dp(4))
        card.bind(
            on_touch_down=lambda widget, touch, fest=festival: (
                self.show_festival_detail(fest) if widget.collide_point(*touch.pos) else False
            )
        )

        name_label = Factory.StyledLabel(
            text=festival["name"],
            font_size="15sp",
            bold=True,
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(32),
        )
        name_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        card.add_widget(name_label)

        date_range_text = (
            f"{festival['start_date'].strftime('%a %d %b %Y')} to "
            f"{festival['end_date'].strftime('%a %d %b %Y')}"
        )
        date_label = Factory.StyledLabel(
            text=date_range_text,
            font_size="10sp",
            bold=True,
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(20),
        )
        date_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        card.add_widget(date_label)

        location_label = Factory.StyledLabel(
            text=festival["location"],
            font_size="10sp",
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(28),
        )
        location_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        card.add_widget(location_label)

        return card

    def get_day_times(self, festival, day):
        if festival["varies_by_day"] and day != festival["start_date"]:
            saved = festival.get("day_times", {}).get(day.isoformat())
            if saved:
                return saved["open"], saved["close"]
        return festival["opening_time"], festival["closing_time"]

    def build_festival_detail(self, festival):
        detail = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12), size_hint_y=None)
        detail.bind(minimum_height=detail.setter("height"))

        back_container = AnchorLayout(
            anchor_x="left", anchor_y="center", size_hint_y=None, height=dp(36)
        )
        back_button = Factory.CancelButton(
            text="< Back", font_size="13sp", size_hint=(None, None), size=(dp(90), dp(36))
        )
        back_button.bind(on_press=lambda instance: self.close_festival_detail())
        back_container.add_widget(back_button)
        detail.add_widget(back_container)

        name_label = Factory.StyledLabel(
            text=festival["name"],
            font_size="20sp",
            bold=True,
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(40),
        )
        name_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        detail.add_widget(name_label)

        date_range_text = (
            f"{festival['start_date'].strftime('%a %d %b %Y')} to "
            f"{festival['end_date'].strftime('%a %d %b %Y')}"
        )
        dates_label = Factory.StyledLabel(
            text=date_range_text,
            font_size="14sp",
            bold=True,
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(24),
        )
        dates_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        detail.add_widget(dates_label)

        day_lines = []
        current_date = festival["start_date"]
        while current_date <= festival["end_date"]:
            open_time, close_time = self.get_day_times(festival, current_date)
            day_lines.append(f"{current_date.strftime('%a %d %b')}: {open_time} - {close_time}")
            current_date += timedelta(days=1)

        hours_label = Factory.StyledLabel(
            text="\n".join(day_lines),
            font_size="12sp",
            halign="center",
            valign="middle",
            size_hint_y=None,
            text_size=(0, None),
        )
        hours_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        hours_label.bind(
            texture_size=lambda label, size: setattr(label, "height", size[1] + dp(6))
        )
        detail.add_widget(hours_label)

        location_label = Factory.StyledLabel(
            text=festival["location"],
            font_size="12sp",
            halign="center",
            valign="middle",
            size_hint_y=None,
            text_size=(0, None),
        )
        location_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        location_label.bind(
            texture_size=lambda label, size: setattr(label, "height", size[1] + dp(10))
        )
        detail.add_widget(location_label)

        maps_container = AnchorLayout(anchor_x="center", size_hint_y=None, height=dp(44))
        maps_button = Factory.RoundedButton(
            text="Open in Google Maps",
            font_size="12sp",
            size_hint=(None, None),
            size=(dp(190), dp(38)),
        )
        maps_button.bind(
            on_press=lambda instance, loc=festival["location"]: self.open_in_maps(loc)
        )
        maps_container.add_widget(maps_button)
        detail.add_widget(maps_container)

        website_container = AnchorLayout(anchor_x="center", size_hint_y=None, height=dp(44))
        website_button = Factory.LinkIcon(
            text="Visit Website",
            font_size="13sp",
            size_hint=(None, None),
            size=(dp(150), dp(36)),
        )
        if festival["website"]:
            website_button.bind(
                on_press=lambda instance, url=festival["website"]: self.open_website(url)
            )
        else:
            website_button.disabled = True
            website_button.opacity = 0.3
        website_container.add_widget(website_button)
        detail.add_widget(website_container)

        edit_container = AnchorLayout(anchor_x="center", size_hint_y=None, height=dp(48))
        edit_button = Factory.RoundedButton(
            text="Edit Festival",
            font_size="13sp",
            size_hint=(None, None),
            size=(dp(160), dp(40)),
        )
        edit_button.bind(on_press=lambda instance, fest=festival: self.open_add_popup(None, fest))
        edit_container.add_widget(edit_button)
        detail.add_widget(edit_container)

        return detail


if __name__ == "__main__":
    FestivalApp().run()