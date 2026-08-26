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


def add_form_row(form, label_text, field, row_size_hint_y=1):
    row = BoxLayout(spacing=dp(0), size_hint_y=row_size_hint_y)
    label = Factory.StyledLabel(text=label_text, font_size="13sp", size_hint_x=0.33)
    label.valign = "middle"
    label.bind(size=label.setter("text_size"))
    row.add_widget(label)
    field.size_hint = (0.67, 0.8)
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
        self.editing_resource_id = None
        self.active_tab = "current"

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
        if tab_name == self.active_tab:
            return
        self.active_tab = tab_name
        self.refresh_nav_bar()
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

        popup_layout = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(5))

        form = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(10),
            size_hint_y=None,
            height=dp(450),
        )

        self.name_input = Factory.StyledTextInput(multiline=True)
        add_form_row(form, "Name:", self.name_input)

        self.location_input = Factory.StyledTextInput(multiline=True)
        add_form_row(form, "Location /\nAddress:", self.location_input)

        self.website_input = Factory.StyledTextInput(multiline=False)
        add_form_row(form, "Website:", self.website_input)

        start_row = BoxLayout(spacing=dp(5))
        self.start_day = Spinner(text=DAYS[0], values=DAYS, font_size="11sp")
        self.start_month = Spinner(text=MONTHS[0], values=MONTHS, font_size="11sp")
        self.start_year = Spinner(text=YEARS[0], values=YEARS, font_size="11sp")
        start_row.add_widget(self.start_day)
        start_row.add_widget(self.start_month)
        start_row.add_widget(self.start_year)
        add_form_row(form, "Start date:", start_row, row_size_hint_y=0.8)

        self.one_day_checkbox = CheckBox(size_hint=(None, None), size=(dp(30), dp(30)))
        self.one_day_checkbox.bind(active=self.toggle_one_day)
        checkbox_row = AnchorLayout(anchor_x="left", anchor_y="center")
        checkbox_row.add_widget(self.one_day_checkbox)
        add_form_row(form, "One day only:", checkbox_row, row_size_hint_y=0.8)

        end_row = BoxLayout(spacing=dp(5))
        self.end_day = Spinner(text=DAYS[0], values=DAYS, font_size="11sp")
        self.end_month = Spinner(text=MONTHS[0], values=MONTHS, font_size="11sp")
        self.end_year = Spinner(text=YEARS[0], values=YEARS, font_size="11sp")
        end_row.add_widget(self.end_day)
        end_row.add_widget(self.end_month)
        end_row.add_widget(self.end_year)
        add_form_row(form, "End date:", end_row, row_size_hint_y=0.8)

        self.start_day.bind(text=self.update_end_date)
        self.start_month.bind(text=self.update_end_date)
        self.start_year.bind(text=self.update_end_date)

        self.time_spinner = Spinner(text=TIMES[0], values=TIMES, font_size="11sp")
        add_form_row(form, "Opening time:", self.time_spinner, row_size_hint_y=0.8)

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

            self.time_spinner.text = festival["opening_time"]

            # Setting .active triggers toggle_one_day, which correctly
            # disables the end-date spinners if this was a one-day event.
            self.one_day_checkbox.active = (festival["start_date"] == festival["end_date"])
        else:
            self.update_end_date()

        popup_layout.add_widget(form)

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

        try:
            start_date = date(
                int(self.start_year.text),
                MONTHS.index(self.start_month.text) + 1,
                int(self.start_day.text),
            )
            if self.one_day_checkbox.active:
                end_date = start_date
            else:
                end_date = date(
                    int(self.end_year.text),
                    MONTHS.index(self.end_month.text) + 1,
                    int(self.end_day.text),
                )
        except ValueError:
            return

        if end_date < start_date:
            return

        opening_time = self.time_spinner.text

        try:
            if self.editing_festival_id:
                database.update_festival(
                    self.editing_festival_id,
                    name,
                    location,
                    start_date,
                    end_date,
                    opening_time,
                    website,
                )
            else:
                database.add_festival(name, location, start_date, end_date, opening_time, website)
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
            height=dp(140),
        )

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
        card = Factory.FestivalCard(orientation="vertical", height=dp(117))

        top_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(6)
        )

        link_icon = Factory.LinkIcon(
            text="Link",
            size_hint=(None, None),
            size=(dp(40), dp(28)),
            pos_hint={"center_y": 0.5},
        )
        if festival["website"]:
            link_icon.bind(
                on_press=lambda instance, url=festival["website"]: self.open_website(url)
            )
        else:
            link_icon.disabled = True
            link_icon.opacity = 0.3
        top_row.add_widget(link_icon)

        name_label = Factory.StyledLabel(
            text=f"{festival['name']} [size=11sp][color=#D2691E] edit[/color][/size]",
            font_size="15sp",
            bold=True,
            halign="center",
            valign="middle",
            markup=True,
        )
        name_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        name_label.bind(
            on_touch_down=lambda label, touch, fest=festival: (
                self.open_add_popup(None, fest)
                if label.collide_point(*touch.pos)
                else False
            )
        )
        top_row.add_widget(name_label)

        card.add_widget(top_row)

        bottom_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56))

        # --- Bottom-left column: date range + opening time ---
        date_column = BoxLayout(orientation="vertical", size_hint_x=0.33)

        date_range_text = (
            f"{festival['start_date'].strftime('%a %d %b %Y')} to "
            f"\n{festival['end_date'].strftime('%a %d %b %Y')}"
        )
        date_label = Factory.StyledLabel(
            text=date_range_text,
            font_size="10sp",
            bold=True,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(36),
        )
        date_label.bind(size=date_label.setter("text_size"))
        date_column.add_widget(date_label)

        time_label = Factory.StyledLabel(
            text=f"Opens at {festival['opening_time']}",
            font_size="10sp",
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(20),
        )
        time_label.bind(size=time_label.setter("text_size"))
        date_column.add_widget(time_label)

        bottom_row.add_widget(date_column)

        # --- Bottom-middle column: wrapped address ---
        location_label = Factory.StyledLabel(
            text=festival["location"],
            font_size="10sp",
            halign="center",
            valign="middle",
            size_hint_x=0.47,
            text_size=(0, None),
        )
        location_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        location_label.bind(texture_size=lambda label, size: setattr(label, "height", size[1]))
        bottom_row.add_widget(location_label)

        # --- Bottom-right column: right-aligned Google Maps button ---
        maps_container = AnchorLayout(
            anchor_x="right",
            anchor_y="center",
            size_hint_x=0.20,
            size_hint_min_x=dp(56),
        )
        maps_button = Factory.RoundedButton(
            text="Google\nMaps",
            font_size="10sp",
            halign="center",
            size_hint_x=None,
            width=dp(56),
        )
        maps_button.bind(
            on_press=lambda instance, loc=festival["location"]: self.open_in_maps(loc)
        )
        maps_container.add_widget(maps_button)
        bottom_row.add_widget(maps_container)
        card.add_widget(bottom_row)

        return card


if __name__ == "__main__":
    FestivalApp().run()