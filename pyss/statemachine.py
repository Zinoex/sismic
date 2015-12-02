from functools import lru_cache


class Event:
    """
    Simple event with a name and (optionally) some data.
    """
    def __init__(self, name: str, data: dict=None):
        self.name = name
        self.data = data

    def __eq__(self, other):
        return isinstance(other, Event) and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return 'Event({})'.format(self.name)


class Transition(object):
    """
    A Transition between two states.
    Transition can be eventless or internal (but not both at once).
    A condition (code as string) can be specified as a guard.
    """

    def __init__(self, from_state: str, to_state: str=None, event: Event=None, guard: str=None, action: str=None):
        self.from_state = from_state
        self.to_state = to_state
        self.event = event
        self.guard = guard
        self.action = action

    @property
    def internal(self):
        return self.to_state is None

    @property
    def eventless(self):
        return self.event is None

    def __repr__(self):
        return 'Transition({}, {}, {})'.format(self.from_state, self.to_state, self.event)


class StateMixin:
    """
    State element with a name.
    """

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.name)

    def __eq__(self, other):
        return isinstance(other, StateMixin) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


class ActionStateMixin:
    """
    State that can define actions on entry and on exit.
    """
    def __init__(self, on_entry: str=None, on_exit: str=None):
        self.on_entry = on_entry
        self.on_exit = on_exit


class TransitionStateMixin:
    """
    A simple state can host transitions
    """

    def __init__(self):
        self.transitions = []

    def add_transition(self, transition):
        """
        :param transition: an instance of Transition
        """
        self.transitions.append(transition)


class CompositeStateMixin:
    """
    Composite state can have children states.
    """
    def __init__(self):
        self.children = []

    def add_child(self, state_name):
        self.children.append(state_name)


class BasicState(StateMixin, TransitionStateMixin, ActionStateMixin):
    """
    A basic state, with a name, transitions, actions, etc. but no children.
    """
    def __init__(self, name: str, on_entry: str=None, on_exit: str=None):
        StateMixin.__init__(self, name)
        TransitionStateMixin.__init__(self)
        ActionStateMixin.__init__(self, on_entry, on_exit)


class CompoundState(StateMixin, TransitionStateMixin, ActionStateMixin, CompositeStateMixin):
    """
    Compound states must have children states.
    """
    def __init__(self, name: str, initial: str, on_entry: str=None, on_exit: str=None):
        StateMixin.__init__(self, name)
        TransitionStateMixin.__init__(self)
        ActionStateMixin.__init__(self, on_entry, on_exit)
        CompositeStateMixin.__init__(self)
        self.initial = initial


class OrthogonalState(StateMixin, TransitionStateMixin, ActionStateMixin, CompositeStateMixin):
    """
    Orthogonal states run their children simultaneously.
    """
    def __init__(self, name: str, on_entry: str=None, on_exit: str=None):
        StateMixin.__init__(self, name)
        TransitionStateMixin.__init__(self)
        ActionStateMixin.__init__(self, on_entry, on_exit)
        CompositeStateMixin.__init__(self)


class HistoryState(StateMixin):
    """
    History state can be either 'shallow' (default) or 'deep'.
    A shallow history state resumes the execution of its parent.
    A deep history state resumes the execution of its parent, and resume
    every (recursively) parent's substate execution.
    """

    def __init__(self, name: str, initial: str=None, deep: bool=False):
        StateMixin.__init__(self, name)
        self.name = name
        self.memory = [initial]
        self.initial = initial
        self.deep = deep


class FinalState(StateMixin, ActionStateMixin):
    """
    Final state has NO transition and is used to detect state machine termination.
    """

    def __init__(self, name: str, on_entry: str=None, on_exit: str=None):
        StateMixin.__init__(self, name)
        ActionStateMixin.__init__(self, on_entry, on_exit)


class StateMachine(object):
    def __init__(self, name: str, initial: str, on_entry: str=None):
        """
        Initialize a state machine.
        :param name: Name of this state machine
        :param initial: Initial state
        :param on_entry: Code to execute before the execution
        """
        self.name = name
        self.initial = initial
        self.on_entry = on_entry
        self.states = {}  # name -> State object
        self.transitions = []  # list of Transition objects
        self.parent = {}  # name -> parent.name
        self.children = []

    def register_state(self, state: StateMixin, parent: str):
        """
        Register given state in current state machine and register it to its parent
        :param state: instance of State to add
        :param parent: name of parent state
        """
        self.states[state.name] = state
        self.parent[state.name] = parent.name if isinstance(parent, StateMixin) else parent

        # Register on parent state
        parent_state = self.states.get(self.parent[state.name], None)
        if parent_state is not None:
            self.states[self.parent[state.name]].add_child(state.name)
        else:
            # ... or on top-level state (self!)
            self.children.append(state.name)

    def register_transition(self, transition: Transition):
        """
        Register given transition in current state machine and register it on the source state
        :param transition: instance of Transition
        """
        self.transitions.append(transition)
        self.states[transition.from_state].add_transition(transition)

    def __repr__(self):
        return 'State machine: {}'.format(self.name)

    @lru_cache()
    def ancestors_for(self, state: str) -> list:
        """
        :param state: name of the state
        :return: ancestors, in decreasing depth
        """
        ancestors = []
        parent = self.parent[state]
        while parent:
            ancestors.append(parent)
            parent = self.parent[parent]
        return ancestors

    @lru_cache()
    def descendants_for(self, state: str) -> list:
        """
        :param state: name of the state
        :return: descendants, in increasing depth
        """
        descendants = []
        states_to_consider = [state]
        while states_to_consider:
            state = states_to_consider.pop(0)
            state = self.states[state]
            if isinstance(state, CompositeStateMixin):
                for child in state.children:
                    states_to_consider.append(child)
                    descendants.append(child)
        return descendants

    @lru_cache()
    def depth_of(self, state: str) -> int:
        """
        Return the depth of the given state, starting from 0 (root, top-level).
        :param state: name of the state
        :return: depth of state
        """
        if state is None:
            return 0
        ancestors = self.ancestors_for(state)
        return len(ancestors) + 1

    @lru_cache()
    def least_common_ancestor(self, s1: str, s2: str) -> str:
        """
        Return the deepest common ancestor for s1 and s2, or None if
        there is no common ancestor except root (top-level) state.
        :param s1: name of first state
        :param s2: name of second state
        :return: name of deepest common ancestor or None
        """
        s1_anc = self.ancestors_for(s1)
        s2_anc = self.ancestors_for(s2)
        for state in s1_anc:
            if state in s2_anc:
                return state

    def leaf_for(self, states: list) -> list:
        """
        Return a subset of `states` that are leaves, ie. return each state from
        `states` that has no descendant in `states`.
        :param states: A list of state names
        :return: A list of state names
        """
        leaves = []
        # TODO: Need a more efficient way to compute this set
        for state in states:
            keep = True
            for descendant in self.descendants_for(state):
                if descendant in states:
                    keep = False
                    break
            if keep:
                leaves.append(state)
        return leaves

    @property
    def valid(self) -> bool:
        """
        Validate current state machine:
         (C1) Check that transitions refer to existing states
         (C2) Check that history can only be defined as a child of a CompoundState
         (C3) Check that history state's initial memory refer to a parent's child
         (C4) Check that initial state refer to a parent's child
         (C5) Check that orthogonal states have at least one child
         (C6) Check that there is no internal eventless guardless transition
        :return: True or raise a ValueError
        """
        # C1 & C6
        for transition in self.transitions:
            if not(transition.from_state in self.states and (not transition.to_state or transition.to_state in self.states)):
                raise ValueError('Transition {} refers to an unknown state'.format(transition))
            if not transition.event and not transition.guard and not transition.to_state:
                raise ValueError('Transition {} is an internal, eventless and guardless transition.'.format(transition))

        for name, state in self.states.items():
            if isinstance(state, HistoryState):  # C2 & C3
                if not isinstance(self.states[self.parent[name]], CompoundState):
                    raise ValueError('History state {} can only be defined in a compound (non-orthogonal) states'.format(state))
                if state.initial and not (self.parent[state.initial] == self.parent[name]):
                    raise ValueError('Initial memory of {} should refer to a child of {}'.format(state, self.parent[name]))

            if isinstance(state, CompositeStateMixin):  # C5
                if len(state.children) <= 0:
                    raise ValueError('Composite state {} should have at least one child'.format(state))

            if isinstance(state, CompoundState):  # C4
                if self.parent[name] and not (self.parent[state.initial] == name):
                    raise ValueError('Initial state of {} should refer to one of its children'.format(state))

        return True
