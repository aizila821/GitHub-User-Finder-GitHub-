import json
import os
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk


API_URL = "https://api.github.com/search/users"
FAVORITES_FILE = Path(__file__).with_name("favorites.json")


class GitHubUserFinder(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("GitHub User Finder")
        self.geometry("840x520")
        self.minsize(720, 460)

        self.search_results = []
        self.favorites = self.load_favorites()

        self.configure(padx=18, pady=16)
        self.create_widgets()
        self.refresh_favorites()

    def create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        search_frame = ttk.Frame(self)
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        search_frame.columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _event: self.start_search())

        self.search_button = ttk.Button(search_frame, text="Найти", command=self.start_search)
        self.search_button.grid(row=0, column=1)

        content = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        content.grid(row=1, column=0, sticky="nsew")

        results_frame = ttk.Labelframe(content, text="Результаты поиска")
        favorites_frame = ttk.Labelframe(content, text="Избранные пользователи")
        content.add(results_frame, weight=3)
        content.add(favorites_frame, weight=2)

        self.create_results_panel(results_frame)
        self.create_favorites_panel(favorites_frame)

        self.status_var = tk.StringVar(value="Введите логин или имя пользователя GitHub.")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status.grid(row=2, column=0, sticky="ew", pady=(12, 0))

    def create_results_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        columns = ("login", "profile", "score")
        self.results_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        self.results_tree.heading("login", text="Логин")
        self.results_tree.heading("profile", text="Профиль")
        self.results_tree.heading("score", text="Рейтинг")
        self.results_tree.column("login", width=150, anchor="w")
        self.results_tree.column("profile", width=270, anchor="w")
        self.results_tree.column("score", width=80, anchor="center")
        self.results_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 8))
        self.results_tree.bind("<Double-1>", lambda _event: self.open_selected_result())

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.results_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=(10, 8))
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(parent)
        actions.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        actions.columnconfigure((0, 1), weight=1)

        ttk.Button(actions, text="Добавить в избранное", command=self.add_selected_to_favorites).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(actions, text="Открыть профиль", command=self.open_selected_result).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

    def create_favorites_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        columns = ("login", "profile")
        self.favorites_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        self.favorites_tree.heading("login", text="Логин")
        self.favorites_tree.heading("profile", text="Профиль")
        self.favorites_tree.column("login", width=150, anchor="w")
        self.favorites_tree.column("profile", width=240, anchor="w")
        self.favorites_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 8))
        self.favorites_tree.bind("<Double-1>", lambda _event: self.open_selected_favorite())

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.favorites_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=(10, 8))
        self.favorites_tree.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(parent)
        actions.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        actions.columnconfigure((0, 1), weight=1)

        ttk.Button(actions, text="Удалить", command=self.remove_selected_favorite).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(actions, text="Открыть профиль", command=self.open_selected_favorite).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

    def start_search(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Проверка ввода", "Поле поиска не должно быть пустым.")
            self.search_entry.focus_set()
            return

        self.set_search_state(is_loading=True)
        thread = threading.Thread(target=self.search_users, args=(query,), daemon=True)
        thread.start()

    def search_users(self, query):
        try:
            users = self.fetch_users(query)
        except Exception as error:
            self.after(0, lambda: self.show_search_error(error))
            return

        self.after(0, lambda: self.show_results(users))

    def fetch_users(self, query):
        params = urllib.parse.urlencode({"q": query, "per_page": 20})
        request = urllib.request.Request(
            f"{API_URL}?{params}",
            headers=self.get_api_headers(),
        )

        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))

        return [
            {
                "login": item["login"],
                "html_url": item["html_url"],
                "avatar_url": item.get("avatar_url", ""),
                "score": round(float(item.get("score", 0)), 2),
            }
            for item in payload.get("items", [])
        ]

    def get_api_headers(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "GitHub-User-Finder-Tkinter",
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def show_results(self, users):
        self.search_results = users
        self.results_tree.delete(*self.results_tree.get_children())

        for index, user in enumerate(users):
            self.results_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(user["login"], user["html_url"], user["score"]),
            )

        if users:
            self.status_var.set(f"Найдено пользователей: {len(users)}.")
        else:
            self.status_var.set("Пользователи не найдены.")

        self.set_search_state(is_loading=False)

    def show_search_error(self, error):
        self.set_search_state(is_loading=False)

        if isinstance(error, urllib.error.HTTPError):
            message = f"GitHub API вернул ошибку {error.code}."
            if error.code == 403:
                message += " Возможно, превышен лимит запросов. Попробуйте позже или укажите GITHUB_TOKEN."
        elif isinstance(error, urllib.error.URLError):
            message = "Не удалось подключиться к GitHub API. Проверьте интернет-соединение."
        else:
            message = str(error)

        self.status_var.set("Ошибка поиска.")
        messagebox.showerror("Ошибка", message)

    def set_search_state(self, is_loading):
        if is_loading:
            self.search_button.configure(state=tk.DISABLED)
            self.status_var.set("Идёт поиск пользователей...")
        else:
            self.search_button.configure(state=tk.NORMAL)

    def add_selected_to_favorites(self):
        user = self.get_selected_result()
        if not user:
            messagebox.showinfo("Избранное", "Выберите пользователя из результатов поиска.")
            return

        if any(favorite["login"].lower() == user["login"].lower() for favorite in self.favorites):
            messagebox.showinfo("Избранное", "Этот пользователь уже есть в избранном.")
            return

        self.favorites.append(
            {
                "login": user["login"],
                "html_url": user["html_url"],
                "avatar_url": user.get("avatar_url", ""),
            }
        )
        self.save_favorites()
        self.refresh_favorites()
        self.status_var.set(f"{user['login']} добавлен в избранное.")

    def remove_selected_favorite(self):
        selected = self.favorites_tree.selection()
        if not selected:
            messagebox.showinfo("Избранное", "Выберите пользователя из избранного.")
            return

        index = int(selected[0])
        login = self.favorites[index]["login"]
        del self.favorites[index]
        self.save_favorites()
        self.refresh_favorites()
        self.status_var.set(f"{login} удалён из избранного.")

    def refresh_favorites(self):
        self.favorites_tree.delete(*self.favorites_tree.get_children())
        for index, user in enumerate(self.favorites):
            self.favorites_tree.insert("", tk.END, iid=str(index), values=(user["login"], user["html_url"]))

    def load_favorites(self):
        if not FAVORITES_FILE.exists():
            return []

        try:
            with FAVORITES_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning("Избранное", "Не удалось прочитать favorites.json. Список будет пустым.")
            return []

        if not isinstance(data, list):
            return []

        return [
            {
                "login": item.get("login", ""),
                "html_url": item.get("html_url", ""),
                "avatar_url": item.get("avatar_url", ""),
            }
            for item in data
            if isinstance(item, dict) and item.get("login") and item.get("html_url")
        ]

    def save_favorites(self):
        with FAVORITES_FILE.open("w", encoding="utf-8") as file:
            json.dump(self.favorites, file, ensure_ascii=False, indent=2)

    def get_selected_result(self):
        selected = self.results_tree.selection()
        if not selected:
            return None
        return self.search_results[int(selected[0])]

    def open_selected_result(self):
        user = self.get_selected_result()
        if not user:
            messagebox.showinfo("Профиль", "Выберите пользователя из результатов поиска.")
            return
        webbrowser.open(user["html_url"])

    def open_selected_favorite(self):
        selected = self.favorites_tree.selection()
        if not selected:
            messagebox.showinfo("Профиль", "Выберите пользователя из избранного.")
            return
        webbrowser.open(self.favorites[int(selected[0])]["html_url"])


if __name__ == "__main__":
    app = GitHubUserFinder()
    app.mainloop()
