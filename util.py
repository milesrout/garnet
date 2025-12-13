import functools
import inspect

def trace(*, include_self=False, restrict=None, name=None):

    def decorator(f):
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args, **kwds):
            ba = sig.bind(*args, **kwds)
            ba.apply_defaults()
            print(f.__name__ if name is None else name, end='(')
            parts = []
            for k, v in ba.arguments.items():
                if include_self or k != 'self':
                    if restrict is None or k in restrict:
                        try:
                            v = v.find()
                        except:
                            pass
                        parts.append(f'{k}={v}')
            print(', '.join(parts), end=')\n')
            return f(*args, **kwds)

        return wrapper

    return decorator
