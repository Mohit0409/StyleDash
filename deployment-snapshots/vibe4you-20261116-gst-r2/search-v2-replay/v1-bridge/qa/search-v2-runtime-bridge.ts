import { scoreProductSearch, scoreStoreSearch, parseSearchQuery, scoreSearchLabel } from '../src/utils/searchEngine';
import { buildSearchSuggestions } from '../src/utils/searchSuggestions';
const api = Object.freeze({ scoreProductSearch, scoreStoreSearch, parseSearchQuery, scoreSearchLabel, buildSearchSuggestions });
Object.defineProperty(globalThis, '__V4Y_SEARCH_V2__', { value: api, configurable: false, writable: false });
