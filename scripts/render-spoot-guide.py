#!/usr/bin/env python3
"""Render the current spoot guide as deterministic, text-first illustrated cards."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    ("Start here", "Verify, get help, then choose your channels.", [
        ("Verify", "Use the server's verification page to unlock the channels your roles allow."),
        ("Choose your channels", "Open Your channels to show or hide eligible channels. Your roles and existing access still apply."),
        ("Need a person?", "DM spoot. Your message reaches the person who runs it, and they can reply through spoot."),
        ("Find your way", "This guide covers member commands, raid signups, automatic updates, recaps, Mythic+ and voice clips.")]),
    ("Member commands", "Type / in a server channel and choose a command.", [
        ("/progress", "See Scrambled's current Heroic raid progress. Only you see the answer."),
        ("/poll", "Create a Discord poll with 2–10 answers, a duration from 1 hour to 7 days, and optional multiple selections. Requires Create Polls."),
        ("/raid", "Open current raid signups, rosters and attendance."),
        ("/clip", "While in voice, start listening or save the funny thing that just happened. See the voice clips card.")]),
    ("Raid events", "Keep your signup current so organizers know who is coming.", [
        ("Find an event", "Run /raid or use the signup posted in your raid channel."),
        ("Choose your signup", "Use the event's buttons and menus to choose attendance, class and specialization where offered."),
        ("Change your plans", "Return to the same event to update your signup. Check the displayed date and time before joining."),
        ("For organizers", "Members with Manage Server can use /create for a guided form or /quickcreate for a single command.")]),
    ("Automatic raid updates", "First kills, milestones and team progress post automatically.", [
        ("First boss kills", "spoot watches connected raid sources and announces qualifying first kills for each configured team."),
        ("Team channels", "Progression, Meer's Raid and Saturday Raid keep their own destinations and progress."),
        ("Ahead of the Curve", "Qualifying Heroic completion is announced with the team's progress."),
        ("No command needed", "These updates run on a schedule. Existing posts and raid records keep their original dates and results.")]),
    ("Raid recaps", "The night's results, with a full scorecard on the website.", [
        ("Read the card", "Open the recap posted to your team's channel for a summary of that raid night."),
        ("Open the full recap", "Follow the link for damage, healing, deaths, damage taken and performance summaries."),
        ("Keep the date in view", "A recap describes its reported raid night. Later corrections are dated on the card and in its text."),
        ("Separate teams", "Progression, Meer's Raid and Saturday Raid have separate pages and delivery channels.")]),
    ("Mythic+", "Guild runs, weekly progress and records in one place.", [
        ("Weekly recap", "Look in the Mythic+ bot channel for the weekly guild recap."),
        ("Full standings", "Open the linked page for standings, rosters and source coverage."),
        ("Guild runs", "The recap covers observed guild runs, timed keys and score growth."),
        ("New records", "spoot posts qualifying guild records and keeps the records page up to date.")]),
    ("spoot's slash commands", "Seven slash commands. Permissions still apply.", [
        ("/progress · everyone", "Shows Scrambled's current Heroic raid progress. Only you see the answer."),
        ("/raid · everyone", "Opens raid signups, rosters and attendance for current events."),
        ("/poll · Create Polls", "Creates a native Discord poll: 2–10 answers, 1 hour to 7 days, optional multiple selections."),
        ("/clip · voice members", "Turns the last five seconds into a soundboard sound you name. First use starts listening."),
        ("/create · Manage Server", "Creates a raid signup with a guided form for title, date, time, timezone and details."),
        ("/quickcreate · Manage Server", "Creates a raid signup in one command, with title and date as options."),
        ("/setup · Manage Server", "Connects the server to a WoW guild and chooses the channel and role for announcements."),
        ("How to run one", "Type / in a channel and choose from spoot's commands. Discord hides commands you cannot use.")]),
    ("Voice clips", "Turn a funny moment into a soundboard sound.", [
        ("1 · Start listening", "Join voice and run /clip. spoot joins, posts a notice and says: spoot is now listening for slash clip commands."),
        ("2 · Catch the moment", "Run /clip again. Only you see the reply with a clip.mp3 player and four buttons."),
        ("3 · Make it fit", "Play the clip. Use A bit earlier or A bit later, then Add to soundboard and give it a name. Throw away discards it."),
        ("4 · Play it", "Stay connected to voice. Open Soundboard below Voice Connected on desktop, or swipe up in the call on a phone. Click a sound to play it."),
        ("What is kept", "Only the last 90 seconds stay in memory until someone clips them. spoot leaves when voice is empty or Stop listening is pressed."),
        ("Shared soundboard", "Members can publish up to three new sounds per day. Administrators are exempt. Everyone can play sounds in voice.")]),
]


def font(size, bold=False):
    return ImageFont.truetype(str(ROOT / 'assets/fonts' / ('Inter-SemiBold.ttf' if bold else 'Inter-Regular.ttf')), size)


def wrap(draw, text, face, width):
    lines, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if line and draw.textlength(candidate, font=face) > width:
            lines.append(line); line = word
        else:
            line = candidate
    return lines + ([line] if line else [])


def render(out):
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for number, (title, subtitle, sections) in enumerate(GUIDES, 1):
        rows = (len(sections) + 1) // 2
        height = 350 + rows * 300 + 85
        image = Image.new('RGB', (1280, height), '#101116'); draw = ImageDraw.Draw(image)
        avatar = Image.open(ROOT/'assets/spoot-avatar.png').convert('RGBA')
        avatar.thumbnail((90, 90)); image.paste(avatar, (42, 20), avatar)
        draw.text((145, 37), 'spoot', font=font(38, True), fill='#f5f3f6')
        draw.text((1040, 50), f'guide {number}/8', font=font(24), fill='#eda1d0')
        draw.line((40, 125, 1240, 125), fill='#66334f', width=2)
        draw.text((44, 165), title, font=font(48, True), fill='#f5f3f6')
        draw.text((44, 235), subtitle, font=font(28), fill='#bbb5c0')
        for index, (heading, body) in enumerate(sections):
            x = 44 + (index % 2) * 612; y = 325 + (index // 2) * 300
            draw.rounded_rectangle((x, y, x+584, y+274), radius=18, fill='#1c1921', outline='#493343', width=2)
            draw.text((x+26, y+25), heading, font=font(25, True), fill='#f05cbb')
            lines=wrap(draw, body, font(27), 530)
            if len(lines)>6:raise ValueError('Guide copy does not fit: '+heading)
            for row,line in enumerate(lines):draw.text((x+26,y+75+row*32),line,font=font(27),fill='#f0ebf1')
        draw.text((44,height-58),'ryangrey.dev  ·  spoot guide  ·  branding updated October 22, 2026',font=font(20),fill='#aba3b0')
        name=f'{number:02d}-spoot-guide.png'; image.save(out/name,optimize=True)
        manifest.append({'file':name,'title':title,'subtitle':subtitle,'sections':sections})
    (out/'guide.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);render(parser.parse_args().output)
