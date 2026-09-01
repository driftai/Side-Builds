import { directMediaProvider } from './direct-media-provider.js';

const providers = new Map();

export function registerMediaProvider(provider) {
  if (!provider?.id || typeof provider.supports !== 'function' || typeof provider.resolve !== 'function') {
    throw new TypeError('Media provider requires id, supports(), and resolve().');
  }
  providers.set(String(provider.id), Object.freeze(provider));
  return provider;
}

export function findMediaProvider(input) {
  return [...providers.values()].find(provider => provider.supports(input)) || null;
}

export function listMediaProviders() {
  return [...providers.values()].map(provider => provider.id);
}

registerMediaProvider(directMediaProvider);
registerMediaProvider({
  id: 'browser-page',
  supports: input => {
    const value = String(input || '').trim();
    return /^https?:\/\//i.test(value) && !directMediaProvider.supports(value);
  },
  resolve: (input, options) => import('./media-resolver.js').then(module => module.resolveMediaPage(input, options))
});
