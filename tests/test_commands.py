"""Tests for bot/commands.py - Command parsing, routing, and property-based tests."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, strategies as st

from bot.commands import (
    COMMANDS,
    get_handler,
    handle_unknown,
    on_message,
    parse_command,
)
from bot.config import Config


# --- Unit Tests ---


class TestParseCommand:
    """Tests for the parse_command function."""

    def test_returns_none_for_non_prefix_message(self):
        assert parse_command("hello world") is None

    def test_returns_none_for_empty_string(self):
        assert parse_command("") is None

    def test_parses_command_with_no_args(self):
        result = parse_command("mpai!play")
        assert result == ("play", [])

    def test_parses_command_with_args(self):
        result = parse_command("mpai!play never gonna give you up")
        assert result == ("play", ["never", "gonna", "give", "you", "up"])

    def test_parses_command_case_insensitive(self):
        result = parse_command("mpai!PLAY something")
        assert result == ("play", ["something"])

    def test_returns_empty_command_for_prefix_only(self):
        result = parse_command("mpai!")
        assert result == ("", [])

    def test_parses_all_known_commands(self):
        for cmd in COMMANDS:
            result = parse_command(f"mpai!{cmd}")
            assert result == (cmd, [])


class TestGetHandler:
    """Tests for the get_handler function."""

    def test_returns_correct_handler_for_known_commands(self):
        for cmd_name, expected_handler in COMMANDS.items():
            assert get_handler(cmd_name) is expected_handler

    def test_returns_handle_unknown_for_unrecognized_command(self):
        assert get_handler("nonexistent") is handle_unknown

    def test_returns_handle_unknown_for_empty_string(self):
        assert get_handler("") is handle_unknown


class TestOnMessage:
    """Tests for the on_message routing function."""

    @pytest.fixture
    def mock_message(self):
        msg = MagicMock()
        msg.author.bot = False
        msg.channel.send = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self, mock_message):
        mock_message.author.bot = True
        mock_message.content = "mpai!play test"
        await on_message(mock_message)
        mock_message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_non_prefix_messages(self, mock_message):
        mock_message.content = "hello world"
        await on_message(mock_message)
        mock_message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_routes_known_command(self, mock_message):
        mock_message.content = "mpai!pause"
        await on_message(mock_message)
        # After implementation, pause replies with feedback when nothing is playing
        mock_message.channel.send.assert_called_once_with("Nothing is currently playing.")

    @pytest.mark.asyncio
    async def test_routes_unknown_command_to_help(self, mock_message):
        mock_message.content = "mpai!foobar"
        await on_message(mock_message)
        call_args = mock_message.channel.send.call_args[0][0]
        assert "Unknown command" in call_args
        assert "Available commands" in call_args


class TestHandleUnknown:
    """Tests for the handle_unknown help message."""

    @pytest.mark.asyncio
    async def test_lists_all_available_commands(self):
        msg = MagicMock()
        msg.channel.send = AsyncMock()
        await handle_unknown(msg, [])
        call_args = msg.channel.send.call_args[0][0]
        for cmd in COMMANDS:
            assert f"`mpai!{cmd}`" in call_args


# --- Property-Based Tests ---


class TestCommandParsingProperty:
    """
    Property-based tests for command parsing and routing.

    **Validates: Requirements 7.1, 7.2**
    """

    @given(command_name=st.sampled_from(list(COMMANDS.keys())))
    def test_known_command_routes_to_correct_handler(self, command_name):
        """P1: Any message with mpai! + known command routes to the correct handler."""
        content = f"{Config.COMMAND_PREFIX}{command_name}"
        parsed = parse_command(content)
        assert parsed is not None
        cmd, args = parsed
        handler = get_handler(cmd)
        assert handler is COMMANDS[command_name]

    @given(
        command_name=st.sampled_from(list(COMMANDS.keys())),
        args_parts=st.lists(st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=65, max_codepoint=122),
            min_size=1,
            max_size=20,
        ), min_size=0, max_size=5),
    )
    def test_known_command_with_args_routes_correctly(self, command_name, args_parts):
        """P1: Known command with arbitrary args still routes to correct handler."""
        args_str = " ".join(args_parts)
        content = f"{Config.COMMAND_PREFIX}{command_name} {args_str}".rstrip()
        parsed = parse_command(content)
        assert parsed is not None
        cmd, args = parsed
        handler = get_handler(cmd)
        assert handler is COMMANDS[command_name]

    @given(
        unknown_cmd=st.text(
            alphabet=st.characters(whitelist_categories=("L",), min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=15,
        ).filter(lambda x: x not in COMMANDS)
    )
    def test_unknown_command_routes_to_help_handler(self, unknown_cmd):
        """P1: Any message with mpai! + unknown command routes to handle_unknown."""
        content = f"{Config.COMMAND_PREFIX}{unknown_cmd}"
        parsed = parse_command(content)
        assert parsed is not None
        cmd, args = parsed
        handler = get_handler(cmd)
        assert handler is handle_unknown
