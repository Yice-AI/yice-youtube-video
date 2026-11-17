#!/usr/bin/env node
import {readUsage,readBudgets,usageSummary} from './media-api.mjs';
const args=process.argv.slice(2),episode=args.includes('--project')?args[args.indexOf('--project')+1]:process.cwd();
console.log(JSON.stringify(usageSummary(readUsage(),{budgets:readBudgets(),episode}),null,2));
