from kdbxtool import Database
from dotenv import load_dotenv
from rich import print
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
import pyperclip
import os
import getpass

load_dotenv()

DB_PATH = os.getenv("DB", r"file.kdbx")

c = Console()


def path(grp):
    parts = []
    cur = grp

    while cur:
        if cur.name:
            parts.append(cur.name)
        cur = getattr(cur, "parent", None)

    return "/" + "/".join(reversed(parts))


def ls(grp):
    tbl = Table(title=path(grp))

    tbl.add_column("#", width=4)
    tbl.add_column("Type", width=8)
    tbl.add_column("Name")

    mapping = {}
    i = 1

    for g in grp.subgroups:
        mapping[i] = ("group", g)
        tbl.add_row(str(i), "📁 DIR", g.name)
        i += 1

    for e in grp.entries:
        mapping[i] = ("cred", e)
        tbl.add_row(
            str(i),
            "🔑 CRED",
            e.title or "(untitled)"
        )
        i += 1

    c.print(tbl)

    return mapping


def show_entry(e, show_pass=True):
    c.print(f"[bold cyan]Title:[/] {e.title}")
    c.print(f"[bold cyan]User:[/] {e.username}")

    if show_pass:
        c.print(f"[bold cyan]Password:[/] {e.password}")

    c.print(f"[bold cyan]URL:[/] {e.url}")


def build_tree(group, node):

    for g in group.subgroups:
        child = node.add(f"[cyan]📁 {g.name}")
        build_tree(g, child)

    for e in group.entries:
        node.add(f"[green]🔑 {e.title}")

try:
    with Database.open(
        DB_PATH,
        password=os.getenv("PASS")
    ) as db:

        current = db.root_group

        c.print("[green]KeePass Shell[/]")
        c.print("type 'help'")

        while True:
            try:
                cmd = input(f"{path(current)}> ").strip()

                if not cmd:
                    continue

                parts = cmd.split()
                action = parts[0]

                # ---------- HELP ----------

                if action == "help":
                    c.print("""
    ls                list current group
    cd N              enter subgroup
    cd ..             go back
    pwd               show path
    view N            show credential
    cat N             alias of view
    cp N              copy password
    new               create credential
    mkdir             create subgroup
    rm N              delete item
    search TEXT       search entire db
    tree              show tree
    quit              exit
    """)

                # ---------- QUIT ----------

                elif action in ("quit", "exit", "q"):
                    break

                # ---------- PWD ----------

                elif action == "pwd":
                    c.print(path(current))

                # ---------- LS ----------

                elif action == "ls":
                    ls(current)

                # ---------- CD ----------

                elif action == "cd":

                    if len(parts) < 2:
                        continue

                    target = " ".join(parts[1:])

                    # cd ..
                    if target == "..":
                        if current.parent:
                            current = current.parent
                        continue

                    # cd by number
                    if target.isdigit():

                        idx = int(target)

                        mapping = ls(current)

                        if idx not in mapping:
                            c.print("[red]invalid index[/]")
                            continue

                        typ, obj = mapping[idx]

                        if typ != "group":
                            c.print("[red]not a group[/]")
                            continue

                        current = obj

                    # cd by group name
                    else:

                        found = next(
                            (
                                g
                                for g in current.subgroups
                                if g.name.lower() == target.lower()
                            ),
                            None,
                        )

                        if found:
                            current = found
                        else:
                            c.print("[red]group not found[/]")


                # ---------- VIEW ----------

                elif action in ("view", "cat"):

                    idx = int(parts[1])
                    mapping = ls(current)

                    typ, obj = mapping[idx]

                    if typ != "cred":
                        c.print("[red]not a credential[/]")
                        continue

                    show_entry(obj)

                # ---------- COPY PASS ----------

                elif action == "cp":

                    idx = int(parts[1])
                    mapping = ls(current)

                    typ, obj = mapping[idx]

                    if typ == "cred":
                        pyperclip.copy(obj.password)
                        c.print("[green]password copied[/]")

                # ---------- NEW ENTRY ----------

                elif action == "new":

                    title = input("Title: ")
                    user = input("Username: ")
                    pwd = getpass.getpass("Password: ")
                    url = input("URL: ")

                    current.add_entry(
                        title=title,
                        username=user,
                        password=pwd,
                        url=url,
                    )

                    db.save()
                    c.print("[green]saved[/]")

                # ---------- NEW GROUP ----------

                elif action == "mkdir":

                    name = input("Group name: ")

                    if hasattr(current, "add_group"):
                        current.add_group(name)
                        db.save()
                        c.print("[green]group created[/]")
                    else:
                        c.print(
                            "[yellow]add_group() not available in your kdbxtool version[/]"
                        )

                # ---------- DELETE ----------

                elif action == "rm":

                    idx = int(parts[1])
                    mapping = ls(current)

                    typ, obj = mapping[idx]

                    confirm = input(
                        f"delete {getattr(obj,'name',getattr(obj,'title','item'))}? [y/N] "
                    )

                    if confirm.lower() != "y":
                        continue

                    obj.delete()
                    db.save()

                    c.print("[green]deleted[/]")

                # ---------- SEARCH ----------

                elif action == "search":

                    if len(parts) < 2:
                        continue

                    query = " ".join(parts[1:]).lower()

                    tbl = Table(title=f"Search: {query}")
                    tbl.add_column("Title")
                    tbl.add_column("User")
                    tbl.add_column("URL")

                    count = 0

                    for e in db.iter_entries():

                        text = " ".join(
                            [
                                str(e.title or ""),
                                str(e.username or ""),
                                str(e.url or ""),
                            ]
                        ).lower()

                        if query in text:
                            tbl.add_row(
                                e.title or "",
                                e.username or "",
                                e.url or "",
                            )
                            count += 1

                    c.print(tbl)
                    c.print(f"[green]{count} result(s)[/]")

                # ---------- TREE ----------

                elif action == "tree":

                    root = Tree(
                        f"[bold yellow]{db.root_group.name}"
                    )

                    build_tree(
                        db.root_group,
                        root
                    )

                    c.print(root)

                else:
                    c.print("[red]unknown command[/]")

            except Exception as e:
                c.print(f"[red]{e}[/]")

except FileNotFoundError:
    c.print(f"[red]Database not found:[/] {DB_PATH}")
except Exception as e:
    c.print(f"[red]Failed to open database:[/] {e}")