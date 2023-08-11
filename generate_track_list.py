import json
import os
import re
import subprocess
import shutil

"""Folder music style description
This is just some descriptive words that I thought of, while listening to each individual track in the 

Befog: slow, thoughtful, hint of melancholy
BehindStorms: Slow, hint of melancholy, hint of eerie
Beyond: slow, homesick, hint of melancholy
BlindingNebula: Slow, uplifting
Exhale: Slow, relaxing, uplifting
Float: Solemn, tempered, relaxed
Found: Quiet, ominous
HappilyLost: Quiet, fragile
Impact: Quiet, brooding, thoughtful
InSight: Quiet, relaxed
Interim: Relaxed, just chilling, neutral to happy
LightDance: Adventurous, upbeat
LongForgotten: Quiet, longing, hint of melancholy 
Particle: Happy, relaxed

"""

print('Avorion soundtrack generator v0.96 by Bitcrusher')

track_types = [
    "Befog",
    "Beyond",
    "BehindStorms",
    "BlindingNebula",
    "Exhale",
    "Float",
    "Found",
    "HappilyLost",
    "Impact",
    "InSight",
    "Interim",
    "LightDance",
    "LongForgotten",   
    "Particle",
]

# Used to create keys for each track, from it's filename
def convert_to_camelcase(string):
    # Remove non-alphanumeric characters
    string = re.sub(r'[^a-zA-Z0-9]', '', string)
    
    # Convert to camel case
    words = string.split()
    camelcase = words[0] + ''.join(word.capitalize() for word in words[1:])
    
    return camelcase


# Replaces the placeholders with values from a dict/key
def replace_placeholders(template, replacements):
    pattern = r"\{\{([^}]+)\}\}"
    matches = re.findall(pattern, template)
    for match in matches:
        for replacement_key in replacements:
            if replacement_key == match:
                placeholder = "{{" + match + "}}"
                # Append the content next to the placeholder
                template = template.replace("{{" + match + "}}", "{{" + match + "}}" + "".join(replacements[replacement_key]))
    
    return template

def check_ffmpeg_present():
    if os.name == 'nt':  # Windows
        ffmpeg_present = os.path.exists("../ffmpeg.exe") and os.path.exists("../ffprobe.exe")
        if not ffmpeg_present:
            print('**** FFmpeg not found to check samplerate/quality of music files ****')
            print('Download from either https://sourceforge.net/projects/ffmpeg-windows-builds/ or https://ffbinaries.com/downloads')
            print('Then place ffmpeg.exe and ffprobe.exe in the same dir as this script and rerun it')
            input("Push any key to continue...")
            quit() # Stopping execution
    else:  # Linux or other Unix-based OS
        ffmpeg_present = os.path.exists("../ffmpeg") and os.path.exists("../ffprobe")
        if not ffmpeg_present:
            print('**** FFmpeg not found to check samplerate/quality of music files ****')
            print('Then place ffmpeg.exe and ffprobe.exe in the same dir as this script and rerun it')
            input("Push any key to continue...")
            quit() # Stopping execution

    return ffmpeg_present

# Checks soundfile for problems
def check_for_problems(filename):
    filepath = filename.replace("\\", "/")
    problems = []
    # TODO change binary path if OS is Linux
    command = [
     "../ffprobe.exe",
        "-v", "error",
        "-show_entries", "stream=index,sample_rate,codec_name",
        "-of", "json",
        filepath
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        data = json.loads(result.stdout)

        for stream in data["streams"]:
            if 'sample_rate' in stream:
                if int(stream['sample_rate']) < 44100: # samplerate above does not appear to crackle
                    problems.append(f' - samplerate {stream['sample_rate']} - may cause crackeling music - should be atleast 44100')
                if stream['codec_name'] != 'vorbis':
                    problems.append(f' - codec is not vorbis - it reported {stream['codec_name']}')

        if len(data["streams"]) > 1:
            if 'sample_rate' in data["streams"][0]:
                problems.append(f' - has more than 1 stream but the first stream IS an audio track, it may still work - found {len(data["streams"])} streams - may cause crashing when being played')
            else:
                problems.append(f' !!! has more than 1 stream and the first stream IS NOT an audio track - found {len(data["streams"])} streams - will likely cause crashing when being played')
        return problems
    
    except subprocess.CalledProcessError as e:
        print(f"Error getting file info: {e}")
        return problems
    

# Remove placeholders from template
def clean_template(template):
    pattern = r"\{\{([^}]+)\}\}" # Match anything {{*}}
    cleaned_template = re.sub(pattern, "", template)
    return cleaned_template

created_folder_structure = False


def create_nested_dirs(nested_structure):
    """
    Check if all directories in the nested structure exist and create them if needed.
    
    Parameters:
        nested_structure (dict or list): The nested dictionary or list representing the directory structure.
                                        For example, {'dir1': {'dir2': {}}, 'dir3': {}} for directory structure
                                        dir1/
                                          └── dir2/
                                        dir3/

    Returns:
        bool: True if all directories exist or have been successfully created, False otherwise.
    """
    def create_nested_dirs_recursively(nested_structure, current_path):
        if isinstance(nested_structure, dict):
            for directory, sub_structure in nested_structure.items():
                new_path = os.path.join(current_path, directory)
                if not os.path.exists(new_path):
                    os.mkdir(new_path)
                    created_folder_structure = True
                create_nested_dirs_recursively(sub_structure, new_path)

        elif isinstance(nested_structure, list):
            for index, sub_structure in enumerate(nested_structure):
                new_path = os.path.join(current_path, str(index))
                if not os.path.exists(new_path):
                    os.mkdir(new_path)
                    created_folder_structure = True
                create_nested_dirs_recursively(sub_structure, new_path)

    if not isinstance(nested_structure, (dict, list)):
        raise ValueError("Input must be a nested dictionary or list.")

    current_path = os.getcwd()
    create_nested_dirs_recursively(nested_structure, current_path)


# All .ogg placed in the root of background, will be put in the "All" category of music
background_folder = "data/music/background"

track_id = 1001 # Mod tracks should start from 1001
replacements = {
    'new_tracktypes': [],
    'new_tracks': [],
    'All': [],
}

new_tracklist = {item: [] for item in track_types}


# Takes a track, formats it's name 
def process_track(folder_path, filename, track_id, ffmpeg_present, subfolder_name=None):
    # TODO dirty stuff doing on here, accessing global vars :P
    trackIdentifier = convert_to_camelcase(os.path.basename(filename).replace(".ogg", "" ))
    if trackIdentifier[0].isnumeric(): # It musn't start with anumber, so we'll just add an X
        trackIdentifier = f'X{trackIdentifier}'
    track_path = os.path.join(folder_path, filename)
    
    if ffmpeg_present: # if ffmpeg present, get samplerate
        problems = []
        problems = check_for_problems(f"{os.getcwd()}\\{track_path}")
        if len(problems):
            problem_files[track_path] = problems

    track_path = track_path.replace('\\', '/') # Must use forward slashes in path to .ogg file in .lua file

    replacements['new_tracks'].append(f"\nTracks[TrackType.{trackIdentifier}{track_id}] = {{type = TrackType.{trackIdentifier}{track_id}, path = \"{track_path}\"}}")
    replacements['new_tracktypes'].append(f"\n\t\t{trackIdentifier}{track_id} = {track_id},") # Adding ID to trackidentifier, in case more tracks have the same name
    replacements['All'].append(f"\n\t\tTrackType.{trackIdentifier}{track_id},")
    if subfolder_name:
        #if subfolder_name not in replacements:
        # replacements[subfolder_name] = []
        new_tracklist[subfolder_name].append(f"\n\t\tTrackType.{trackIdentifier}{track_id},")


# Soundfiles with samplerate different from 44100
problem_files = {}

track_collections = {}

nested_dict = {'data': {
    'scripts': {'lib': {}},
    'music': {
        'action': {},
        'background': 
            {
            'Befog': {},
            'BehindStorms': {},
            'Beyond': {},
            'BlindingNebula': {},
            'Exhale': {},
            'Float': {},
            'Found': {},
            'HappilyLost': {},
            'Impact': {},
            'InSight': {},
            'Interim': {},
            'LightDance': {},
            'LongForgotten': {},
            'Particle': {},
        },
        'menu': {}}
    }
}


# Arrow for indicating a folder level
next_level = chr(int('21B3', 16))
 
print("-- Folder structure and theme description")
print(f"{next_level} data")
print(f"  {next_level} music")
print(f"    {next_level} action: Combat music - MUST be called combat0.ogg, combat1.ogg, combat2.ogg etc. - unsure if it supports above 9")
print(f"    {next_level} background: music put in the background folder, will be put in the category called 'All'")
print(f"      {next_level} Befog: slow, thoughtful, hint of melancholy")
print(f"      {next_level} BehindStorms: Slow, hint of melancholy, hint of eerie")
print(f"      {next_level} Beyond: slow, homesick, hint of melancholy")
print(f"      {next_level} BlindingNebula: Slow, uplifting")
print(f"      {next_level} Exhale: Slow, relaxing, uplifting")
print(f"      {next_level} Float: Solemn, tempered, relaxed")
print(f"      {next_level} Found: Quiet, ominous")
print(f"      {next_level} HappilyLost: Quiet, fragile, happy")
print(f"      {next_level} Impact: Quiet, brooding, thoughtful")
print(f"      {next_level} InSight: Quiet, relaxed")
print(f"      {next_level} Interim: Relaxed, just chilling, neutral to happy")
print(f"      {next_level} LightDance: Adventurous, upbeat")
print(f"      {next_level} LongForgotten: Quiet, longing, hint of melancholy ")
print(f"      {next_level} Particle: Happy, relaxed")
print(f"    {next_level} menu: Start menu music - MUST be called title.ogg")


# Check if needed folderstructure is present
if not os.path.exists('PersonalAvorionSoundtrack'):
    os.mkdir('PersonalAvorionSoundtrack') # Make dir
    os.chdir('PersonalAvorionSoundtrack') # Change working dir
    create_nested_dirs(nested_dict)
    
    # Copy modinfo file in an OS agnostic way
    with open('../modinfo.lua', 'rb') as source_file, open('modinfo.lua', 'wb') as destination_file: 
        destination_file.write(source_file.read())
    
    # A small soundtile used to fill in when a category of tracktypes is empty
    with open('../silence.ogg', 'rb') as source_file, open(f'{background_folder}/silence.ogg', 'wb') as destination_file: 
        destination_file.write(source_file.read())

    print("\nNecessary directory structure created in PersonalAvorionSoundtrack - run script again after you've filled the dirs with music in .ogg format")
    print('You can use sites like https://audio.online-convert.com/convert-to-ogg to convert your audio file to .ogg')
    input("Push any key to continue...")
    quit() # Stopping execution
else:
    os.chdir('PersonalAvorionSoundtrack')

print(f"\n\nYou can use sites like https://audio.online-convert.com/convert-to-ogg to convert your audio file to .ogg")

# Find out if the original Avorion music should be kept or discarded
keep_original_music = False
while True:
    print("\nWould you like to keep the original Avorion music alongside the new music or only the new music:")
    print("1. Add new tracks while also keeping original Avorion music tracks")
    print("2. Only new music tracks")

    user_input = input("Enter your choice (1 or 2): ")

    if user_input == '1':
        keep_original_music = True
        break   
    elif user_input == '2':
        # Don't keep original music
        break
    else:
        print("Invalid choice. Please try again.")


# Check if ffmpeg and ffprobe is available
ffmpeg_present = check_ffmpeg_present()

if not ffmpeg_present: # Stop if FFmpeg not found
    print('**** FFmpeg not found to check samplerate/quality of music files ****')
    print('Download from either https://sourceforge.net/projects/ffmpeg-windows-builds/ or https://ffbinaries.com/downloads')
    print('Then place ffmpeg.exe and ffprobe.exe in the same dir as this script and rerun it')
    input("Push any key to continue...")
    quit() # Stopping execution
    
else: # Start generating values for placesholders in music.lua.template
    
    files_processed = 0 # Just for process indication

    # TODO this should be a more generic method instead of duped code - can't be arsed :P
    # First process tracks in the background folder

    for filename in os.listdir(background_folder):
        if filename == 'silence.ogg': # If silence.ogg add with a special trackid
            process_track(background_folder, filename, 99999, ffmpeg_present)
        elif filename.endswith(".ogg"):
            # Get just the filename, strip .ogg and camelcase it
            process_track(background_folder, filename, track_id, ffmpeg_present)
            # Increase track ID for next track
            track_id += 1

        files_processed += 1
        if files_processed % 10 == 0:
            print(f'... processed {files_processed} files')

    # Then process tracks in subfolders of background
    for subfolder_name in track_types:
        folder_path = os.path.join(background_folder, subfolder_name)

        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith(".ogg"):
                    # Get just the filename, strip .ogg and camelcase it
                    process_track(folder_path, filename, track_id, ffmpeg_present, subfolder_name)
                    # Increase track ID for next track
                    track_id += 1
                
                files_processed += 1
                if files_processed % 10 == 0:
                    print(f'... processed {files_processed} files')


if len(replacements['new_tracks']) == 0:
    print("No .ogg files found - .mp3 is not supported")
    exit()


# Load up template
if keep_original_music:
    with open("..\\music.lua.template") as file:
        template = file.read()
else: # Don't keep original music
    with open("..\\music-no-stock-music.lua.template") as file:
        template = file.read()

silence_mood_ignores = []


collection_moods = {
    'Happy': ['BlindingNebula','Exhale','Float','InSight','Particle','LightDance','Interim'],
    'Neutral': ['BehindStorms','Beyond','HappilyLost'],
    'Middle': ['Found','Befog','Impact','LongForgotten'],
    'Melancholic': ['Found','Impact'],
    'HappyNoParticle': ['BlindingNebula','Exhale','Float','InSight','LightDance','Interim'],
    'Cold': ['BlindingNebula','HappilyLost','Beyond','Befog','LongForgotten'],
    'Desolate': ['BehindStorms','Beyond','LongForgotten','Found'],
    'HappyNeutral': ['BehindStorms', 'BlindingNebula','Exhale','HappilyLost','Interim'],
}

# Add each track to the 'mood'/category of music it fits in 
for new_track_category in new_tracklist:
    for new_track in new_tracklist[new_track_category]:
        for mood in collection_moods:
            if new_track_category in collection_moods[mood]:
                if mood not in replacements:
                    replacements[mood] = []
                replacements[mood].append(new_track)

# Only need to potentially add silence tracks when original music is disabled
if not keep_original_music:
    for mood in collection_moods:
        if mood not in replacements:
            replacements[mood] = [f'TrackType.silence99999,']


# Add values to template
populated_template = replace_placeholders(template=template, replacements=replacements)
populated_template = clean_template(template=populated_template)

# Write generated .lua file
lua_file = open("./data/scripts/lib/music.lua", "w")
lua_file.write(populated_template)
lua_file.close()

if len(problem_files):
    print('\nThe following tracks have possible issues:')
    for problem_file_name in problem_files:
        print(problem_file_name)
        print("\n".join(problem_files[problem_file_name]))
    print("\n** Files that has comments with !!! in front of them are critical and needs to be handled! **")

print(f"\nModded music.lua generated - added {len(replacements['new_tracks'])} new tracks")
print(f'Copy the folder PersonalAvorionSoundtrack folder, to %AppData%/Avorion/mods')
print('and enable the mod "Personal Avorion Soundtrack" from the mod menu')
input("\nPush any key to continue...")
