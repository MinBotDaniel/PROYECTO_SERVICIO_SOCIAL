import flet as ft

def main(page: ft.Page):
    page.title = "ZenCore"
    page.add(ft.Text(value="¡Hola! Sistema de ventas listo.", size=30))

ft.app(main)