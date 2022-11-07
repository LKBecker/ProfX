 <h3>ProfX - a powerful TelePath</h3>

  <p>
    ProfX is a python-based client for the TelePath LIMS, able to retrieve and process a variety of data semi-automatically.
    <br />
</p>

<!-- GETTING STARTED -->
## Getting Started
To get a local copy up and running follow these simple steps:
* install python v3.7 or later
* clone repository
* create a `config.py` with your local TelePath instance's commands, IP address, *et cetera*. See `example_config.py` for the required layout and data.
Inside your config.py: 
* Define a function to validate sample IDs, and bind it to check_sample_id. If your sample ID system does not require or implement validation, simply return True.
* Define a function to determine whether a screen is the main menu or not, by examining a list of strings representing the lines of the screen. Bind it to check_main_screen.

### Prerequisites
* Python v3.7 or later
* matplotlib, for advanced features
* a computer able to connecte to your target LIMS (many are intranet-only)
  
<!-- USAGE EXAMPLES -->
## Usage
Use main.py to run commands. 
A CLI may be accessed via the CLI() function (enabled by default)

<!-- ROADMAP -->
## Roadmap


<!-- LICENSE -->
## License
Distributed under the MIT License. See `LICENSE` for more information.
