# Writing CHUD Programs

This short guide teaches the current CHUD language through examples you can run
in the browser studio or with `python chud.py <file>.chud`.

## Your first program

Use `yap` to print a value.

```chud
yap "hello from CHUD"
```

You can print numbers, booleans, variables, and expressions too.

```chud
let score = 7
yap score
yap score + 3
yap W
```

## Variables

Declare a variable with `let`. To change it later, write its name followed by
`=`—without `let`.

```chud
let name = "Ava"
let points = 10

points = points + 5
yap name + " has " + points + " points"
```

CHUD has these value types:

| Type | Examples |
| --- | --- |
| Integer | `0`, `42`, `-8` |
| Float | `3.14`, `0.5` |
| String | `"hello"` |
| Boolean | `W` (true), `L` (false) |

Strings use double quotes. At this stage, escape sequences such as `\"` are not supported.

## Math and comparisons

```chud
let apples = 8
let friends = 3

yap apples + friends
yap apples - friends
yap apples * friends
yap apples / friends
yap apples >= friends
```

`*` and `/` run before `+` and `-`. Use parentheses when you want a different order.

```chud
yap 2 + 3 * 4
yap (2 + 3) * 4
```

`+` also joins text with another value, which makes simple messages easy:

```chud
let level = 4
yap "Current level: " + level
```

## Making decisions with `check`

Use `check` for an if statement. Add `otherwise` for the alternative path.

```chud
let age = 19

check age >= 18 {
    yap "You can enter."
} otherwise {
    yap "Not yet."
}
```

Conditions can use `==`, `!=`, `<`, `<=`, `>`, and `>=`.

```chud
let password = "chud"

check password == "chud" {
    yap "Access granted"
} otherwise {
    yap "Access denied"
}
```

`L`, `0`, and `""` are false in a condition; other values are true.

## Repeating work with `keep`

Use `keep` for a while loop.

```chud
let count = 1

keep count <= 3 {
    yap "Count: " + count
    count = count + 1
}
```

Use `stop` to exit the nearest loop early.

```chud
let number = 0

keep number < 10 {
    number = number + 1
    check number == 4 {
        yap "Stopping at " + number
        stop
    }
}
```

`stop` only works inside a `keep` loop. CHUD also stops a loop after 100,000 iterations to avoid accidental infinite loops.

## Reading input with `hear`

`hear` pauses for one input value. You can give the user a prompt.

```chud
let name = hear "What is your name? "
yap "Nice to meet you, " + name
```

If a response looks like a number, CHUD converts it automatically.

```chud
let first = hear "First number: "
let second = hear "Second number: "
yap "Total: " + (first + second)
```

In the browser studio, all required inputs appear together in one dialog before the program runs.

## Reusing code with `make`

Use `make` to declare a function. Parameters are written in parentheses and separated by commas. Call a function by writing its name with arguments.

```chud
make greet(name) {
    yap "Hello, " + name
}

greet("Ava")
```

Use `return` when a function needs to give a value back to its caller.

```chud
make add(first, second) {
    return first + second
}

let total = add(4, 6)
yap total
```

Function parameters and variables declared inside a function are local to that function. A function must be declared before it is called, and `return` may only be used inside a `make` block.

## Classic `for` loops with `loop`

`keep` is CHUD's while loop. For a classic initializer-condition-update loop, use `loop` so the two forms stay easy to tell apart.

```chud
loop let i = 0; i <= 3; i = i + 1 {
    yap i
}
```

The parts are: initialize `i`, keep running while the condition is true, then update `i` after each pass. The loop variable is local to the loop and is not available afterward. `stop` can still leave the loop early.

```chud
loop let i = 0; i < 10; i = i + 1 {
    check i == 4 {
        stop
    }
    yap i
}
```

## Comments

Start a comment with `//`. Everything after it on the same line is ignored.

```chud
// Track the player's score.
let score = 0
score = score + 10 // Award a bonus.
yap score
```

## A complete mini-program

Save this as `greeting.chud`, then run `python chud.py greeting.chud` or paste it into the studio.

```chud
let name = hear "Your name: "
let attempts = 0

keep attempts < 3 {
    let guess = hear "What is 2 + 2? "
    attempts = attempts + 1

    check guess == 4 {
        yap "Correct, " + name + "!"
        stop
    } otherwise {
        yap "Try again."
    }
}

yap "Thanks for playing."
```

## Common mistakes

| Mistake | Fix |
| --- | --- |
| `score = 1` before declaring `score` | Write `let score = 1` first |
| Missing `{` or `}` | Every `check`, `otherwise`, and `keep` block needs braces |
| `stop` outside a loop | Use `stop` only inside `keep` |
| `"two" - 1` | Arithmetic other than string `+` needs numbers |
| `yap hello` | Use `yap "hello"` for text, or declare a variable named `hello` |

## Where to go next

Try the included [guessing game](game.chud) and [calculator](rizz_calculator.chud), then open the AST and CST views to see how your program is represented internally.
