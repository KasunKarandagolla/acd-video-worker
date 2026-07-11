# Social Sentiment and Public Expectation Evidence

Use this when a title claims `nobody expected`, `everyone doubted`, `written off`, or similar.

## Required evidence

```yaml
public_expectation_evidence:
  source_type: punditry | odds | social_media | press | fan_reaction | user_supplied
  claim: string
  source: string
  timestamp_or_date: string
  supports_nobody_expected: true | false | partial
  confidence: low | medium | high
```

## Rule

Do not claim `nobody expected` unless at least one verified public-expectation source supports it. If not supported, soften the title to `harder than expected`, `almost slipped away`, or `the win that felt like survival`.
