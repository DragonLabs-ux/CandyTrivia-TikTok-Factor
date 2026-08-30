import 'dotenv/config';

const requiredEnv = (name: string): string => {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
};

const bufferGraphQL = async <T>(query: string, variables: Record<string, unknown> = {}): Promise<T> => {
  const response = await fetch('https://api.buffer.com', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${requiredEnv('BUFFER_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({query, variables}),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Buffer API failed (${response.status}): ${text}`);
  const payload = JSON.parse(text) as {data?: T; errors?: Array<{message?: string}>};
  if (payload.errors?.length) {
    throw new Error(`Buffer GraphQL error: ${payload.errors.map((error) => error.message).join('; ')}`);
  }
  if (!payload.data) throw new Error('Buffer returned no data.');
  return payload.data;
};

export const discoverBufferChannels = async () => {
  const organizations = await bufferGraphQL<{
    account: {organizations: Array<{id: string; name: string}>};
  }>(`query Organizations { account { organizations { id name } } }`);

  const results: Array<{organization: string; id: string; name: string; service: string}> = [];
  for (const organization of organizations.account.organizations) {
    const channels = await bufferGraphQL<{
      channels: Array<{id: string; name: string; service: string}>;
    }>(
      `query Channels($organizationId: OrganizationId!) {
        channels(input: {organizationId: $organizationId}) { id name service }
      }`,
      {organizationId: organization.id},
    );
    for (const channel of channels.channels) {
      results.push({organization: organization.name, ...channel});
    }
  }
  return results;
};
