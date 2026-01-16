# Eye-Tracking Integration

This document describes how to integrate Pupil Labs eye-tracking with the PAD Salience Annotation system.

## Overview

The system uses **AprilTag markers** displayed on screen to enable **surface tracking** with Pupil Labs eye trackers. This allows gaze data to be mapped to the PAD image coordinate system.

```
┌─────────────────────────────────────────────────────┐
│  [Tag 0]                              [Tag 3]       │
│                                                     │
│           ┌───────────────────────┐                 │
│           │                       │                 │
│           │     PAD Card Image    │                 │
│           │                       │                 │
│           └───────────────────────┘                 │
│                                                     │
│  [Tag 7]                              [Tag 4]       │
└─────────────────────────────────────────────────────┘
```

## Hardware Requirements

- **Pupil Core** or **Pupil Invisible** eye tracker from [Pupil Labs](https://pupil-labs.com/)
- Computer running **Pupil Capture** software

## AprilTag Configuration

The interface displays 4 AprilTags from the **tag36h11** family at the corners of the PAD image:

| Position | Tag ID | File |
|----------|--------|------|
| Top-left | 0 | `assets/apriltags/tag36h11_0.png` |
| Top-right | 3 | `assets/apriltags/tag36h11_3.png` |
| Bottom-left | 7 | `assets/apriltags/tag36h11_7.png` |
| Bottom-right | 4 | `assets/apriltags/tag36h11_4.png` |

### Why tag36h11?

- Default family supported by Pupil Capture
- 36-bit encoding with 11-bit hamming distance
- Good error correction for reliable detection
- Supported by AprilTag library

### Tag Requirements

- Tags need **white borders** for reliable detection
- The interface displays tags with 8px white padding
- Tags are 60x60px on screen (scaled from 10x10px source)

## Setup Workflow

### 1. Start the Annotation Server

```bash
./run_prototype.sh
# Opens at http://localhost:8765
```

### 2. Configure Pupil Capture

1. Open **Pupil Capture**
2. Enable the **Surface Tracker** plugin
3. The software should auto-detect the 4 AprilTags displayed on screen

### 3. Define the Surface

1. In Pupil Capture, click **Add Surface**
2. Name it "PAD_Image" or similar
3. The software will use the 4 detected tags to define the surface bounds
4. Adjust corners if needed to match the PAD image area precisely

### 4. Start Recording

1. In Pupil Capture, start recording
2. In the annotation interface, select a drug sample
3. Start audio recording and annotate as usual
4. Pupil Capture will record gaze positions mapped to the surface

## Data Export from Pupil Capture

After a session, Pupil Capture exports several files:

### Marker Detections (`marker_detections.csv`)

Records detected AprilTag positions per frame:

```csv
world_index,marker_uid,corner_0_x,corner_0_y,corner_1_x,corner_1_y,...
1110,apriltag_v3:tag36h11:0,274.49,206.49,295.16,207.05,...
```

### Gaze Positions on Surface (`gaze_positions_on_surface_PAD_Image.csv`)

Gaze coordinates mapped to the defined surface:

```csv
world_index,x_norm,y_norm,on_surface,confidence
6207,0.45,0.32,True,0.98
```

- `x_norm`, `y_norm`: Normalized coordinates (0-1) within the surface
- `on_surface`: Whether gaze is on the defined surface
- `confidence`: Gaze detection confidence

## Data Integration

### Synchronization

Both systems record timestamps:
- Annotation tool: `timestamp_start_ms`, `timestamp_end_ms` relative to recording start
- Pupil Capture: `world_index` (frame numbers at capture framerate)

To synchronize:
1. Note the **start time** of both recordings
2. Align based on timestamp or use a visual sync marker

### Coordinate Mapping

The annotation tool uses **normalized coordinates (0-999)**.
Pupil gaze data uses **normalized coordinates (0-1)**.

To convert Pupil gaze to annotation coordinates:
```python
annotation_x = gaze_x_norm * 999
annotation_y = gaze_y_norm * 999
```

## Future Enhancements

### Potential Integrations

1. **Live gaze overlay** - Display gaze position in real-time on the annotation canvas
2. **Automatic region detection** - Use gaze fixations to suggest annotation regions
3. **Gaze heatmaps** - Generate attention heatmaps per PAD image
4. **Fixation analysis** - Automatic detection of fixations and saccades

### Pupil Labs Network API

Pupil Capture can broadcast data via ZeroMQ:
- Topic: `surface` for surface-mapped gaze
- Could enable real-time integration in future versions

## References

- [Pupil Labs Surface Tracking Docs](https://docs.pupil-labs.com/core/software/pupil-capture/#surface-tracking)
- [AprilTag Tag Family Images](https://github.com/AprilRobotics/apriltag-imgs)
- [tag36h11 Specification](https://github.com/AprilRobotics/apriltag-imgs/tree/master/tag36h11)
