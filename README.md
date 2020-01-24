# Understanding video streaming algorithms in the wild

In this repo you'll find all the data to resample and recreate the measurements done
for the PAM2020 paper "Understanding video streaming algorithms in the wild"

### Folder Structure
```
.
+-- BrowserControl
|   +-- MitmServer.py # Man in the middle proxy; DEPRECATED
|   +-- NetworkController.py # Sets up Proxy and Browser
+-- Data
|   +-- Libraries # Browsermobproxy, Chromedriver and AdBlocker
|   +-- Traces # Tested Traces
|   +-- VideoInformation #Information Extracted from the videos of the different providers
|   +-- SelectedVideoDataframe.csv # .csv containing information about the selected videos
+-- FeedbackSampler
|   +-- Implementations # Implementation for different providers
|   +-- Interfaces # Interface needed for different implementations
|   +-- FeedbackSampler.py # Samples the player data while streaming
+-- OfflineSimulator
|   +-- MPC.py # Robust MPC Implementation 
|   +-- OfflineSimulator.py # Offline simulation environment 
+-- TrafficController
|   +-- Interfaces # Interface for throttling policies
|   +-- Implementations # Implementation of different throttling policies
|   +-- BWEstimator.py # BW estimator 
|   +-- TCController.py # Base class traffic controller
|   +-- TCFeedbackControllerChunk.py # Traffic controller for non-dynamic chunk sized providers
|   +-- TCFeedbackControllerContinuous.py # Traffic controller for dynamic chunk sized providers
+-- MainMethods.py # Main sampling and traffic control loop
+-- SampleExample.py # Example of how to sample a given provider with files and a given policy
```

### Prerequisites
The scripts were tested and developed for Python 3.7. Use requirements.txt to install the packages we need

### Example

You can find an example of how to use the scripts in "SampleExample.py"

## Authors

* **Maximilian Grüner** - [ETH Zürich](mgruener@ethz.ch)
* **Melissa Licciardello** - [ETH Zürich](melissa.licciardello@inf.ethz.ch)


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details


