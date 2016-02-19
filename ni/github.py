import enum
import http
import typing as t

from aiohttp import web

from . import abc


LABEL_PREFIX = 'CLA: '
CLA_OK = LABEL_PREFIX + '✓'
NO_CLA = LABEL_PREFIX + '✗'


@enum.unique
class PullRequestEvent(enum.Enum):
    # https://developer.github.com/v3/activity/events/types/#pullrequestevent
    assigned = "assigned"
    unassigned = "unassigned"
    labeled = "labeled"
    unlabeled = "unlabeled"
    opened = "opened"
    closed = "closed"
    reopened = "reopened"
    synchronize = "synchronize"


JSONType = t.Union[str, int, float, bool, None, t.Mapping['JSONType'],
                   t.List['JSONType']]


class Host(abc.ContribHost):

    """Implement a webhook for GitHub pull requests."""

    route = 'POST', '/github'

    _useful_actions =  {PullRequestEvent.opened.value,
                        PullRequestEvent.unlabeled.value,
                        PullRequestEvent.synchronize.value}

    def __init__(self, event: PullRequestEvent, request: JSONType):
        """Represent a contribution."""
        self.event = event
        self.request = request

    @classmethod
    async def process(cls, request):
        """Process the pull request."""
        # https://developer.github.com/webhooks/creating/#content-type
        if request.content_type != 'application/json':
            msg = ('can only accept application/json, '
                   'not {}').format(request.content_type)
            raise abc.ResponseExit(
                    status=http.HTTPStatus.UNSUPPORTED_MEDIA_TYPE, text=msg)

        payload = await request.json()
        if 'zen' in payload:
            # A ping event; nothing to do.
            # https://developer.github.com/webhooks/#ping-event
            raise abc.ResponseExit(status=http.HTTPStatus.NO_CONTENT)
        elif payload['action'] not in cls._useful_actions:
            raise abc.ResponseExit(status=http.HTTPStatus.NO_CONTENT)
        elif payload['action'] == PullRequestEvent.opened.value:
            return cls(PullRequestEvent.opened, payload)
        elif payload['action'] == PullRequestEvent.unlabeled.value:
            label = payload['label']['name']
            if not label.startswith(LABEL_PREFIX):
                raise abc.ResponseExit(status=http.HTTPStatus.NO_CONTENT)
            return cls(PullRequestEvent.unlabeled, payload)
        elif payload['action'] == PullRequestEvent.synchronize.value:
            return cls(PullRequestEvent.synchronize, payload)
        else:  # pragma: no cover
            # Should never happen.
            msg = "don't know how to handle a {!r} event".format(
                payload['action'])
            raise TypeError(msg)

    async def get(self, url: str) -> JSONType:
        """Make a GET request for some JSON data.

        Abstracted out for easy testing w/o requiring internet access.
        """
        response = await aiohttp.get(url)
        return (await response.json())

    async def usernames(self):
        """Return an iterable with all of the contributors' usernames."""
        pull_request = self.request['pull_request']
        # Start with the author of the pull request.
        logins = {pull_request['user']['login']}
        # Fetch the commit data for the pull request.
        commits = await self.get(pull_request['commits_url'])
        # For each commit, get the author and committer.
        for commit in commits:
            commit_data = commit['commit']
            logins.add(commit_data['author']['login'])
            logins.add(commit_data['committer']['login'])
        return frozenset(logins)

    async def update(self, status):
        # XXX
        return web.Response(status=501)    # pragma: no cover