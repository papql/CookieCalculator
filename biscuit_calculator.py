"""A biscuit-themed desktop calculator made with Python's built-in Tkinter."""

import ast
import math
import operator
import tkinter as tk
from pathlib import Path


COLORS = {
    "page": "#FFF9EC",
    "biscuit": "#F5D477",
    "biscuit_edge": "#EFC45A",
    "crumb": "#DBB55C",
    "display": "#DCF7F3",
    "display_edge": "#D2AD51",
    "number": "#C9782E",
    "operator": "#F49355",
    "text": "#FFF8DB",
    "shadow": "#D5A941",
}

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def evaluate_safely(expression: str) -> float:
    """Evaluate numbers, parentheses, and the four basic operations only."""
    if len(expression) > 100:
        raise ValueError("Expression is too long")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(node.value):
                raise ValueError("Invalid number")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Unsupported expression")

    return visit(ast.parse(expression, mode="eval"))


def zero_division_message(expression: str) -> str:
    """Describe the division-by-zero case in a mathematically helpful way."""
    tree = ast.parse(expression, mode="eval")
    divisions = [node for node in ast.walk(tree) if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)]
    for division in reversed(divisions):
        try:
            denominator = evaluate_safely(ast.unparse(division.right))
            numerator = evaluate_safely(ast.unparse(division.left))
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
            continue
        if denominator == 0:
            return "Indeterminate" if numerator == 0 else "Undefined"
    return "Undefined"


class BiscuitCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Biscuit Calculator")
        self.geometry("473x496")
        self.resizable(False, False)
        self.configure(bg="white")
        self.expression = ""
        self.just_evaluated = False
        self.open_parentheses = 0
        self.display_text = "0"
        # How far the display has been scrolled back from the newest digits.
        self.display_offset = 0
        self.click_regions = []

        self.canvas = tk.Canvas(self, width=473, height=496, bg="white", highlightthickness=0)
        self.canvas.pack()
        self.draw_design()
        self.bind_keyboard()

    def rounded_rectangle(self, x1, y1, x2, y2, radius, **options):
        points = [x1+radius,y1, x2-radius,y1, x2,y1, x2,y1+radius,
                  x2,y2-radius, x2,y2, x2-radius,y2, x1+radius,y2,
                  x1,y2, x1,y2-radius, x1,y1+radius, x1,y1, x1+radius,y1]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=18, **options)

    def draw_design(self):
        # Use the original biscuit image instead of drawing it with Tkinter.
        design_path = Path(__file__).with_name("biscuit_design.png")
        if not design_path.exists():
            raise FileNotFoundError(
                "Keep biscuit_design.png in the same folder as this Python file."
            )
        self.design_image = tk.PhotoImage(file=design_path)
        self.canvas.create_image(0, 0, image=self.design_image, anchor="nw")

        # The live number sits inside the blank blue screen in the artwork.
        self.display_item = self.canvas.create_text(
            236, 145, text="0", anchor="e", fill="#657052",
            font=("Arial Rounded MT Bold", 20, "bold")
        )

        layout = [
            [("1", "1"), ("2", "2"), ("3", "3"), ("×", "*")],
            [("4", "4"), ("5", "5"), ("6", "6"), ("÷", "/")],
            [("7", "7"), ("8", "8"), ("9", "9"), ("+", "+")],
            [(".", "."), ("0", "0"), ("( )", "()"), ("−", "-")],
            [("C", "C"), ("=", "=")],
        ]
        x_positions = [93, 139, 184, 229]
        y_positions = [188, 235, 281, 328, 374]
        for row, items in enumerate(layout):
            for col, (_label, value) in enumerate(items):
                x, y = x_positions[col], y_positions[row]
                self.click_regions.append((x, y, x + 39, y + 39, value))
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.configure(cursor="arrow")
        return

    def on_click(self, event):
        for x1, y1, x2, y2, value in self.click_regions:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.press(value)
                break

    def bind_keyboard(self):
        for char in "0123456789.+-*/()":
            self.bind(char, lambda event, c=char: self.press(c))
        self.bind("<Return>", lambda _event: self.press("="))
        self.bind("<KP_Enter>", lambda _event: self.press("="))
        self.bind("<Escape>", lambda _event: self.press("C"))
        self.bind("<BackSpace>", lambda _event: self.backspace())
        self.bind("<Left>", lambda _event: self.scroll_display_left())
        self.bind("<Right>", lambda _event: self.scroll_display_right())

    def press(self, value: str):
        if value == "C":
            self.clear()
            return
        if value == "=":
            self.calculate()
            return
        if value == "()":
            value = "(" if self.open_parentheses == 0 or self.needs_operand() else ")"

        if self.just_evaluated:
            if value not in "+-*/":
                self.expression = ""
                self.open_parentheses = 0
            self.just_evaluated = False

        if value == "(" and self.expression and (self.expression[-1].isdigit() or self.expression[-1] in ".)"):
            self.expression += "*"
        if value.isdigit() and self.expression.endswith(")"):
            self.expression += "*"
        if value == "." and not self.decimal_allowed():
            return
        if value in "+*/" and (not self.expression or self.expression[-1] in "+-*/("):
            return
        if value == "-" and self.expression.endswith("-"):
            return
        if value == ")" and (self.open_parentheses == 0 or self.needs_operand()):
            return
        if value in "+-*/" and self.expression and self.expression[-1] in "+-*/":
            self.expression = self.expression[:-1]

        self.expression += value
        self.display_offset = 0
        if value == "(":
            self.open_parentheses += 1
        elif value == ")":
            self.open_parentheses -= 1
        self.update_display()

    def needs_operand(self):
        return not self.expression or self.expression[-1] in "+-*/("

    def decimal_allowed(self):
        if self.expression.endswith(")"):
            return False
        number = self.expression.replace("-", "+").replace("*", "+").replace("/", "+").replace("(", "+").split("+")[-1]
        return "." not in number

    def calculate(self):
        if not self.expression:
            return
        try:
            expression = self.expression + ")" * self.open_parentheses
            result = evaluate_safely(expression)
            if not math.isfinite(result):
                raise ValueError("Invalid result")
            self.expression = f"{result:.12g}"
            self.display_offset = 0
            self.open_parentheses = 0
            self.just_evaluated = True
            self.update_display()
        except ZeroDivisionError:
            self.display_text = zero_division_message(expression)
            font_size = 15 if self.display_text == "Indeterminate" else 18
            self.canvas.coords(self.display_item, 179, 145)
            self.canvas.itemconfigure(
                self.display_item, text=self.display_text, anchor="center",
                font=("Arial Rounded MT Bold", font_size, "bold")
            )
            self.expression = ""
            self.open_parentheses = 0
            self.just_evaluated = True
        except (SyntaxError, ValueError, TypeError, OverflowError):
            self.display_text = "Error"
            self.canvas.coords(self.display_item, 179, 145)
            self.canvas.itemconfigure(self.display_item, text=self.display_text, anchor="center")
            self.expression = ""
            self.open_parentheses = 0
            self.just_evaluated = True

    def backspace(self):
        if self.expression:
            removed = self.expression[-1]
            self.expression = self.expression[:-1]
            self.display_offset = 0
            if removed == "(":
                self.open_parentheses -= 1
            elif removed == ")":
                self.open_parentheses += 1
            self.update_display()

    def clear(self):
        self.expression = ""
        self.open_parentheses = 0
        self.just_evaluated = False
        self.display_text = "0"
        self.display_offset = 0
        self.canvas.coords(self.display_item, 229, 145)
        self.canvas.itemconfigure(
            self.display_item, text=self.display_text, anchor="e",
            font=("Arial Rounded MT Bold", 20, "bold")
        )

    def update_display(self):
        pretty = self.expression.replace("*", "×").replace("/", "÷").replace("-", "−")
        max_chars = 9

        if not pretty:
            self.display_offset = 0
            self.display_text = "0"
        else:
            # Keep the text inside the blue screen
            max_offset = max(0, len(pretty) - max_chars)
            self.display_offset = min(self.display_offset, max_offset)

            end = len(pretty) - self.display_offset
            start = max(0, end - max_chars)
            self.display_text = pretty[start:end]

        self.canvas.coords(self.display_item, 229, 145)
        self.canvas.itemconfigure(
            self.display_item, text=self.display_text, anchor="e",
            font=("Arial Rounded MT Bold", 20, "bold")
        )

    def scroll_display_left(self):
        """Show earlier numbers when the full expression is wider than the screen."""
        pretty = self.expression.replace("*", "×").replace("/", "÷").replace("-", "−")
        max_offset = max(0, len(pretty) - 9)

        if self.display_offset < max_offset:
            self.display_offset += 1
            self.update_display()

    def scroll_display_right(self):
        """Move back toward the newest numbers in the expression."""
        if self.display_offset > 0:
            self.display_offset -= 1
            self.update_display()


if __name__ == "__main__":
    BiscuitCalculator().mainloop()
