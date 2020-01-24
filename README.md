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
+-- TrafficController
|   +-- Interfaces # Interface for throttling policies
|   +-- Implementations # Implementation of different throttling policies
|   +-- BWEstimator.py # BW estimator 
|   +-- TCController.py # Base class traffic controller
|   +-- TCFeedbackControllerChunk.py # Traffic controller for non-dynamic chunk sized providers
|   +-- TCFeedbackControllerContinuous.py # Traffic controller for dynamic chunk sized providers
+-- MainMethods.py # Main sampling and traffic control loop
+-- SampleVimeoExample.py # Example of how to sample a given provider with files and a given policy
```

### Prerequisites

To be able to use all throttling methods you need to install tcconfig
```
pip install tcconfig
```

### Example

You can find an example of how to use the scripts in "SampleVimeoExample.py"

## Authors

* **Maximilian Grüner** - [ETH Zürich](mgruener@ethz.ch)
* **Melissa Licciardello ** - [ETH Zürich](melissa.licciardello@inf.ethz.ch)


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details


