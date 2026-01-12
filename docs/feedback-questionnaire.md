# PAD Salience Annotation System - Feedback Questionnaire

We're building a system to capture expert annotations on PAD (Paper Analytical Device) card images. Your feedback will help us create a tool that works well for everyone.

---

## For Specialists (Annotators)

### Workflow

1. **How long do you typically spend analyzing a single PAD card?**
   - [ ] Less than 1 minute
   - [ ] 1-3 minutes
   - [ ] 3-5 minutes
   - [ ] More than 5 minutes

2. **When analyzing a PAD card, do you:**
   - [ ] Look at all 12 lanes systematically
   - [ ] Focus only on lanes relevant to the expected drug
   - [ ] Scan the whole card first, then focus on specific areas
   - [ ] Other: _____________

3. **What information do you typically note when analyzing a PAD card?**
   - [ ] Color intensity in specific lanes
   - [ ] Color comparison between lanes
   - [ ] Presence/absence of expected reactions
   - [ ] Artifacts or quality issues
   - [ ] Other: _____________

4. **Would you prefer to:**
   - [ ] Annotate images in a fixed sequence (assigned order)
   - [ ] Choose which images to annotate
   - [ ] Have a mix (some assigned, some choice)

### Annotation Tools

5. **For marking regions on the image, what would you prefer?**
   - [ ] Rectangle/box selection (simpler, faster)
   - [ ] Freehand drawing (more precise for irregular areas)
   - [ ] Both options available
   - [ ] Point clicking (just mark a spot)

6. **When marking a region, what's most important to capture?**
   - [ ] The exact area you're looking at
   - [ ] Which lane(s) are involved
   - [ ] The color/reaction you observe
   - [ ] All of the above

7. **Is automatic lane detection (based on where you draw) helpful, or would you prefer to manually select lanes?**
   - [ ] Automatic detection is helpful
   - [ ] I prefer manual selection
   - [ ] Both options would be ideal

### Audio Recording

8. **Are you comfortable recording audio explanations while annotating?**
   - [ ] Yes, very comfortable
   - [ ] Somewhat comfortable
   - [ ] Prefer typing explanations
   - [ ] Prefer not to explain (just mark regions)

9. **If recording audio, would you prefer to:**
   - [ ] Record continuously while annotating (natural flow)
   - [ ] Start/stop recording for each region (more structured)
   - [ ] Record a summary at the end

10. **What language would you primarily use for explanations?**
    - [ ] English
    - [ ] Spanish
    - [ ] French
    - [ ] Portuguese
    - [ ] Other: _____________

### Time & Effort

11. **How many PAD card images could you realistically annotate in one session?**
    - [ ] 5-10 images
    - [ ] 10-20 images
    - [ ] 20-50 images
    - [ ] More than 50 images

12. **How often could you participate in annotation sessions?**
    - [ ] Daily
    - [ ] A few times per week
    - [ ] Weekly
    - [ ] Occasionally

13. **What would make the annotation process easier or faster?**
    - Open response: _____________

---

## For Administrators / Researchers

### Experiment Management

14. **How many specialists do you expect to participate in a typical experiment?**
    - [ ] 1-3
    - [ ] 3-10
    - [ ] 10-20
    - [ ] More than 20

15. **How many images would a typical experiment include?**
    - [ ] 10-50 images
    - [ ] 50-100 images
    - [ ] 100-500 images
    - [ ] More than 500 images

16. **Do you need multiple specialists to annotate the same images?**
    - [ ] Yes, for inter-annotator agreement
    - [ ] No, one annotation per image is enough
    - [ ] Depends on the experiment

17. **How would you like to select images for an experiment?**
    - [ ] By drug type
    - [ ] By concentration level
    - [ ] By difficulty (easy/hard cases)
    - [ ] Random sampling
    - [ ] Manual selection
    - [ ] All of the above

### Quality Control

18. **What quality checks would be valuable?**
    - [ ] Minimum number of annotations per image
    - [ ] Minimum audio duration
    - [ ] Review/approval workflow
    - [ ] Flagging problematic annotations
    - [ ] Other: _____________

19. **Should specialists be able to see each other's annotations?**
    - [ ] No, keep them independent
    - [ ] Yes, after they complete their own
    - [ ] Only for training purposes

### Data Export

20. **What formats do you need for exported data?**
    - [ ] JSON/JSONL
    - [ ] CSV
    - [ ] HuggingFace datasets format
    - [ ] COCO format
    - [ ] Custom format: _____________

21. **Do you need audio transcriptions included in exports?**
    - [ ] Yes, automatic transcription (AI-generated)
    - [ ] Yes, manual transcription
    - [ ] Audio files only (transcribe separately)
    - [ ] Not needed

---

## For PAD Domain Experts

### Annotation Content

22. **What types of observations are most important to capture?**
    - [ ] Presence/absence of expected color
    - [ ] Color intensity levels
    - [ ] Comparison between lanes
    - [ ] Artifacts and quality issues
    - [ ] Unexpected reactions
    - [ ] Other: _____________

23. **Should specialists categorize their annotations? If yes, what categories?**
    - [ ] No categories needed
    - [ ] Positive/negative reaction
    - [ ] Expected/unexpected
    - [ ] Normal/artifact/issue
    - [ ] Custom categories: _____________

24. **What makes a PAD card image "difficult" to analyze?**
    - Open response: _____________

25. **Are there specific drugs or reactions that are harder to identify?**
    - Open response: _____________

### Training Data Quality

26. **What would make the annotations more useful for training AI models?**
    - [ ] More detailed explanations
    - [ ] Standardized terminology
    - [ ] Multiple expert opinions per image
    - [ ] Confidence levels
    - [ ] Other: _____________

27. **Should we capture the specialist's confidence level for each annotation?**
    - [ ] Yes, high/medium/low
    - [ ] Yes, numeric scale (1-5)
    - [ ] No, not needed

28. **What common mistakes should we help specialists avoid?**
    - Open response: _____________

---

## General Feedback

29. **What features are MUST-HAVE for you to use this system?**
    - Open response: _____________

30. **What features would be NICE-TO-HAVE but not essential?**
    - Open response: _____________

31. **What concerns do you have about the proposed system?**
    - Open response: _____________

32. **Any other feedback or suggestions?**
    - Open response: _____________

---

## Contact

Please send your responses or discuss further:
- GitHub Issues: https://github.com/psaboia/pad-salience-annotations/issues
- Or contact the project team directly

Thank you for your feedback!
