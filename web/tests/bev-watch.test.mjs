import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { WORKSPACE_STORAGE, briefingText, emptyWorkspace, isPublicPage, loadWorkspace, parseWorkspace, restoreProduct, saveWorkspace } from "../src/lib/bev-watch.ts";

afterEach(()=>{ delete globalThis.localStorage; delete process.env.NEXT_PUBLIC_BEV_WATCH_MODE; });

test("public routes normalize slash variants while the local root stays with the engine",()=>{
  assert.equal(isPublicPage("/workspace"),true);
  assert.equal(isPublicPage("/onboarding/"),true);
  assert.equal(isPublicPage("/"),false);
  assert.equal(isPublicPage("/keys/"),false);
  process.env.NEXT_PUBLIC_BEV_WATCH_MODE="hosted-preview";
  assert.equal(isPublicPage("/"),true);
});

test("an exported portfolio round trips without losing review decisions",()=>{
  const workspace={...emptyWorkspace(),company:"Example Beverages",categories:["Non-alcoholic beverages"],markets:["United States"],sources:["fda"],reviewed:["label"],saved:["ingredient"],completed:true,products:[{id:"example",name:"Lemon Tea",category:"Non-alcoholic beverages",ingredients:"Tea, lemon",markets:["United States"]}]};
  const data=new Map();
  globalThis.localStorage={getItem:name=>data.get(name)??null,setItem:(name,value)=>data.set(name,value)};
  assert.equal(saveWorkspace(workspace),true);
  assert.deepEqual(loadWorkspace(),workspace);
  assert.deepEqual(parseWorkspace(JSON.parse(data.get(WORKSPACE_STORAGE))),workspace);
});

test("malformed imports, unknown markets, and duplicate product identities are rejected",()=>{
  const product={id:"example",name:"Tea",category:"Non-alcoholic beverages",ingredients:"Tea",markets:["United States"]};
  for(const value of [null,[],{}, {...emptyWorkspace(),cadence:"Hourly"}, {...emptyWorkspace(),sources:["unknown"]}, {...emptyWorkspace(),markets:["unknown"]}, {...emptyWorkspace(),products:[{...product,markets:[]}]}, {...emptyWorkspace(),products:[product,product]}]) assert.equal(parseWorkspace(value),null);
});

test("blocked storage never reports a successful save and corrupt storage recovers",()=>{
  globalThis.localStorage={setItem:()=>{throw new Error("Storage blocked");},getItem:()=>"broken JSON"};
  assert.equal(saveWorkspace(emptyWorkspace()),false);
  assert.deepEqual(loadWorkspace(),emptyWorkspace());
});

test("undo after importing a deleted product preserves the imported record and reloads",()=>{
  const removed={id:"example",name:"Tea",category:"Non-alcoholic beverages",ingredients:"Tea",markets:["United States"]};
  const imported={...emptyWorkspace(),products:[{...removed,name:"Updated Tea"}]};
  const restored={...imported,products:restoreProduct(imported.products,removed)};
  assert.equal(restored.products.length,1);
  assert.equal(restored.products[0].name,"Updated Tea");
  assert.deepEqual(parseWorkspace(JSON.parse(JSON.stringify(restored))),restored);
});

test("exported briefings carry sample status and never claim monitoring is live",()=>{
  const text=briefingText({...emptyWorkspace(),company:"Example Beverages"});
  assert.match(text,/Bev Watch \| Example Beverages/);
  assert.match(text,/synthetic examples, not current regulatory information/);
  assert.match(text,/No live monitoring or email delivery is active/);
  assert.match(text,/Not legal advice/);
});
