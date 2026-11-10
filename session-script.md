# Session script

This script is for the formal calibration pilot. It is written to be read aloud
or paraphrased consistently. Do not add hints about the experimental conditions
or the expected answers.

## 1. Before the participant arrives

- Confirm consent materials and ethics reference.
- Start the application and open a fresh browser profile.
- Check that the database path is the pilot database, not the dry-run database.
- Have the sequence assignment ready.
- Silence notifications.

## 2. Welcome and consent

> Thanks for coming. This session is part of a study about how people use
> recommendations when they work on short Python tasks. It should take about
> 60 to 75 minutes.
>
> I will ask you to read some short programs, answer questions about them, rate
> how confident you are, and then decide whether to change your answer after
> seeing a recommendation. Some recommendations will be correct and some will
> be incorrect. That is part of the study. Your job is to use your own judgment,
> not to agree with the recommendation.
>
> Participation is voluntary. You can stop at any time without giving a reason
> and without any penalty. I will not record audio or video. Your answers are
> stored under a study code, not your name.
>
> Please read the information sheet and sign the consent form if you agree.

Check that the consent form is signed before continuing.

## 3. Interface introduction

> Here is how the session works. On each trial you will see a short Python task.
> First, answer it yourself. Then rate how confident you are that your answer is
> correct. After that, a recommendation appears.
>
> In some trials, a verification panel is available. You can open it and inspect
> the evidence. In other trials, no verification is available. The message will
> tell you. You can still decide for yourself.
>
> After the recommendation, you give your final answer. You can keep your
> initial answer or change it. There is no penalty for changing or for keeping
> it.
>
> There are 18 tasks, in three blocks, with a short break between blocks. Two
> practice trials come first. The practice trials are only to learn the
> interface; they are not part of the analysis.

### 3.1 Confidence scale

> The confidence slider goes from 0 to 100.
>
> - 0–20: I am guessing.
> - 21–40: I am unsure.
> - 41–60: I am somewhat confident.
> - 61–80: I am confident.
> - 81–100: I am very confident.
>
> Please use the whole scale. There is no right or wrong confidence rating.

### 3.2 Recommendation

> The recommendation is a suggestion from an AI assistant. It may be right or
> wrong. Treat it as advice, not as an answer key.

### 3.3 Evidence

> When verification is available, you can open the panel. It may show a test, a
> trace, or a comparison. You can look for as long as you like, or not at all.
> When it is not available, you will see: “No verification is available for this
> trial. Continue with your own judgment.”

## 4. Practice trials

> Let's do two practice trials. They use the same interface but are not part of
> the study. Please think aloud if you are comfortable; otherwise just work as
> you normally would.

After each practice trial, check:

- Did the participant find the answer controls?
- Did they understand the confidence slider?
- Did they see the recommendation?
- Did they find the evidence panel?
- Did they understand how to submit the final answer?

Do not give feedback on the correctness of their answers. Give feedback only on
the interface.

> Any questions before we start the real tasks?

## 5. Main trials

> We will now start the first block. Please work carefully but at a natural pace.
> Keep this browser tab focused. If you need a break, wait for the break screen
> between blocks. If something goes wrong, tell me immediately.

During the trials:

- Do not answer the task for the participant.
- Do not explain the recommendation.
- Do not say whether the recommendation is correct.
- If the participant asks whether they are doing it right, say: “Use your own
  judgment; the recommendation may be right or wrong.”
- If the interface fails, pause and record the problem.

### 5.1 Block break

> You have finished this block. Take a short break. When you are ready, press
> Continue. The next block uses the same interface but a different set of tasks.

### 5.2 Final trial

> This is the last task. After you submit, there is a short questionnaire about
> the interface and your strategy.

## 6. Completion questionnaire

Read the questions as written in the application. Give the participant privacy
to answer. If they ask what a question means, paraphrase without suggesting an
answer.

Suggested prompts:

- How clear were the task instructions?
- How useful was the recommendation?
- How useful was the verification panel when it was available?
- What strategy did you use to decide whether to change your answer?
- Did you notice any technical problems?
- Is there anything else you want to add?

## 7. Debrief

> Thank you. I can now explain the design. The study compares three ways of
> offering verification: no verification, verification that is always available,
> and verification that is available only when confidence is low. Some
> recommendations were deliberately incorrect. We are interested in how people
> decide whether to rely on a recommendation, not in whether they agree with it.
>
> Your data are stored under a study code. You can withdraw your data until
> [date / analysis start]. Do you have any questions?

Answer questions factually. Do not reveal the calibration values or the expected
direction of the main results.

## 8. Closing

> Thank you for your time. Here is the compensation / participation confirmation.
> If you think of anything else, contact [researcher contact].

Record:

- session completed;
- any deviations;
- questionnaire issues;
- compensation given;
- debrief completed.

## 9. Dry-run variant

For the technical dry run, use the welcome text in `dry-run-plan.md` instead.
Do not ask for consent, do not record trial data as research data, and do not run
the completion questionnaire. The goal is interface feedback only.
