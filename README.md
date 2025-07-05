# turnjet

[https://github.com/Sovxx/turnjet](https://github.com/Sovxx/turnjet)

Record aircraft turns around a set location using data from [adsb.lol](https://adsb.lol).

![example_map](documentation/example_map.jpg "example_map").
![example_plot](documentation/example_plot.jpg "example_plot").

## Installation

1. Install **Python 3+**
2. Install the libraries listed in `requirements.txt`:

   ```
   pip install -r requirements.txt
   ```
3. Set up your `config.ini` file
4. Start the application:

   ```
   python main.py
   ```
   (After stopping, wait 2 hours before restarting to avoid discontinuities and fake turns)
5. Wait for at least 2 hours
6. Generate map:

   ```
   python map.py
   ```