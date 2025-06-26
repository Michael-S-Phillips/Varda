from typing import runtime_checkable, Protocol, Callable


@runtime_checkable
class Operator(Protocol):
    """
    A protocol defining the interface for Varda operators.
    Operators should implement this interface to be recognized by the Varda application.
    """

    v_name: str
    v_description: str

    run: Callable[[any], None]

    def run(self, context) -> None:
        """
        Run the operator with the given arguments.
        """
        ...
