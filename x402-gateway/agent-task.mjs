// LLM-driven autonomous research agent: given a task, an LLM plans the search
// queries, the agent autonomously PAYS for each via x402, then the LLM synthesizes
// a final cited answer. Demonstrates an AI spending money to complete a task, with
// the spend flowing to the human creators of the knowledge it used.
import OpenAI from 'openai'
import { runAgentSearch } from './agent-core.mjs'

const num = (x) => Number(x ?? 0)

async function planQueries(openai, model, task) {
  const r = await openai.chat.completions.create({
    model,
    temperature: 0.2,
    messages: [
      {
        role: 'system',
        content:
          'You are a research agent with access to a paid knowledge network. Break the user task ' +
          'into 2-3 focused search queries that, answered together, would let you complete it. ' +
          'Return ONLY a JSON array of short query strings, nothing else.',
      },
      { role: 'user', content: task },
    ],
  })
  const text = (r.choices[0].message.content ?? '[]').replace(/```json|```/g, '').trim()
  try {
    const arr = JSON.parse(text)
    return Array.isArray(arr) ? arr.slice(0, 3).map(String) : [task]
  } catch {
    return [task]
  }
}

async function synthesize(openai, model, task, searches) {
  const context = searches
    .map((s, i) => `[Finding ${i + 1} — query "${s.query}"]\n${s.answer ?? '(no answer)'}`)
    .join('\n\n---\n\n')
  const r = await openai.chat.completions.create({
    model,
    temperature: 0.2,
    messages: [
      {
        role: 'system',
        content:
          'You are a research agent. Using ONLY the findings below (each is a grounded answer the ' +
          'agent PAID for from a knowledge network), write a clear, well-structured answer to the ' +
          'user task. Cite findings inline like (Finding 1). If the findings are insufficient, say so.',
      },
      { role: 'user', content: `Task: ${task}\n\nFindings:\n${context}` },
    ],
  })
  return r.choices[0].message.content ?? ''
}

/**
 * Run the full agentic loop. Returns
 * { task, plan, searches, finalAnswer, economics }.
 */
export async function runAgentTask(task, { agentSecret, gatewayUrl, network, openaiKey, model }) {
  const openai = new OpenAI({ apiKey: openaiKey })

  const plan = await planQueries(openai, model, task)

  // Pay for every planned query in parallel (fast mode: the per-creator USDC payout settles in
  // the background, so we don't serialize on settlement latency). Order is preserved; a single
  // failed query degrades to an empty result instead of aborting the whole task.
  const searches = await Promise.all(
    plan.map((query) =>
      runAgentSearch(query, { agentSecret, gatewayUrl, network, fast: true }).catch((e) => ({
        ok: false,
        query,
        steps: [{ label: 'Search failed', detail: String(e?.message ?? e) }],
        answer: null,
        owners: [],
        distribution: null,
      })),
    ),
  )

  const usable = searches.filter((s) => s.answer)
  const finalAnswer = usable.length ? await synthesize(openai, model, task, usable) : null

  // Economics: tally what the agent spent and what creators earned.
  let totalSpent = 0
  let creatorsPaid = 0
  for (const s of searches) {
    if (s.paid) totalSpent += num(s.paid.amount)
    for (const d of s.distribution?.distributed ?? []) creatorsPaid += num(d.amount)
  }

  return {
    task,
    plan,
    searches,
    finalAnswer,
    economics: {
      searchCount: searches.length,
      totalSpentStroops: totalSpent,
      creatorsPaidStroops: creatorsPaid,
      platformStroops: totalSpent - creatorsPaid,
    },
  }
}
